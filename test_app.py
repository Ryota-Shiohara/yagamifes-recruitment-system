import sqlite3
import tempfile
import unittest

import app as app_module


class RecruitmentAppTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = self.temp_directory.name + '/test.db'
        connection = sqlite3.connect(self.database_path)
        with open('schema.sql', encoding='utf-8') as schema_file:
            connection.executescript(schema_file.read())
        with open('seed.sql', encoding='utf-8') as seed_file:
            connection.executescript(seed_file.read())
        connection.close()

        app_module.DATABASE = self.database_path
        app_module.app.config['TESTING'] = True
        self.client = app_module.app.test_client()

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute('PRAGMA foreign_keys = ON')
        connection.row_factory = sqlite3.Row
        return connection

    def test_main_pages_render(self) -> None:
        paths = (
            '/',
            '/applicants/new?bureau_id=1',
            '/applicants',
            '/applicants/101',
            '/applicants/101/edit',
            '/bureau-schedules',
            '/bureau-schedules/1/edit',
            '/interviewers',
            '/interviewers/1/evaluations',
            '/interviewers/1/applicants/101/scores',
            '/rankings?bureau_id=1',
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_role_selection_separates_navigation_and_routes(self) -> None:
        def page_text(response):
            return response.get_data(as_text=True)

        entry = self.client.get('/')
        self.assertEqual(entry.status_code, 200)
        self.assertIn('応募者として入る', page_text(entry))
        self.assertNotIn('応募者一覧', page_text(entry))

        applicant_home = self.client.get(
            '/role/applicant', follow_redirects=True,
        )
        self.assertEqual(applicant_home.status_code, 200)
        self.assertIn('応募者メニュー', page_text(applicant_home))
        self.assertNotIn('応募者一覧', page_text(applicant_home))
        self.assertEqual(self.client.get('/manager/applicants').status_code, 302)
        self.assertEqual(self.client.get('/applicants').status_code, 302)

        self.client.get('/')
        manager_home = self.client.get(
            '/role/bureau_manager', follow_redirects=True,
        )
        self.assertEqual(manager_home.status_code, 200)
        self.assertIn('局責任者メニュー', page_text(manager_home))
        self.assertIn('/manager/applicants', page_text(manager_home))
        self.assertEqual(
            self.client.get('/applicant/applications/new').status_code, 302,
        )

        self.client.get('/')
        interviewer_home = self.client.get(
            '/role/interviewer', follow_redirects=True,
        )
        self.assertEqual(interviewer_home.status_code, 200)
        self.assertIn('面接官メニュー', page_text(interviewer_home))
        self.assertNotIn('応募者一覧', page_text(interviewer_home))
        self.assertEqual(self.client.get('/manager/rankings').status_code, 302)

    def test_assignment_board_updates_schedule_and_creates_custom_slot(self) -> None:
        self.client.get('/role/bureau_manager')
        board = self.client.get('/manager/bureau-schedules?bureau_id=1')
        self.assertEqual(board.status_code, 200)
        self.assertIn('面接割り当てボード', board.get_data(as_text=True))

        response = self.client.post('/manager/assignments', data={
            'applicant_id': '202',
            'bureau_schedule_id': '1',
        })
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.get_json()['success'])

        response = self.client.post('/manager/assignments', data={
            'applicant_id': '202',
            'bureau_schedule_id': '5',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])
        connection = self.connect()
        confirmed = connection.execute(
            '''SELECT confirmed_bureau_schedule_id FROM applicants
               WHERE id = 202''',
        ).fetchone()[0]
        connection.close()
        self.assertEqual(confirmed, 5)

        response = self.client.post('/manager/assignments', data={
            'applicant_id': '202',
            'bureau_schedule_id': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])

        response = self.client.post('/manager/bureau-schedules', data={
            'bureau_id': '2',
            'schedule_id': '',
            'start_at': '2026-07-13T12:00',
            'end_at': '2026-07-13T12:30',
        })
        self.assertEqual(response.status_code, 302)
        connection = self.connect()
        created_count = connection.execute(
            '''SELECT COUNT(*)
               FROM bureau_schedules AS bureau_schedule
               JOIN schedules AS schedule
                 ON schedule.id = bureau_schedule.schedule_id
               WHERE bureau_schedule.bureau_id = 2
                 AND schedule.start_at = '2026-07-13 12:00:00'
                 AND schedule.end_at = '2026-07-13 12:30:00' ''',
        ).fetchone()[0]
        connection.close()
        self.assertEqual(created_count, 1)

    def test_manager_can_create_and_edit_criteria_for_selected_bureau(self) -> None:
        self.client.get('/role/bureau_manager')
        response = self.client.get('/manager/criteria?bureau_id=2')
        self.assertEqual(response.status_code, 200)
        self.assertIn('発信力・企画力', response.get_data(as_text=True))

        response = self.client.post('/manager/criteria', data={
            'bureau_id': '2',
            'name': '新しい採用基準',
            'description': '新しい基準の説明',
        })
        self.assertEqual(response.status_code, 302)
        connection = self.connect()
        criterion = connection.execute(
            '''SELECT id, bureau_id, name, description FROM criteria
               WHERE bureau_id = 2 AND name = ?''',
            ('新しい採用基準',),
        ).fetchone()
        connection.close()
        self.assertIsNotNone(criterion)
        self.assertEqual(criterion['bureau_id'], 2)

        response = self.client.post(
            f"/manager/criteria/{criterion['id']}/edit",
            data={
                'bureau_id': '2',
                'name': '更新した採用基準',
                'description': '更新した説明',
            },
        )
        self.assertEqual(response.status_code, 302)
        connection = self.connect()
        updated = connection.execute(
            'SELECT name, description FROM criteria WHERE id = ?',
            (criterion['id'],),
        ).fetchone()
        connection.close()
        self.assertEqual(
            (updated['name'], updated['description']),
            ('更新した採用基準', '更新した説明'),
        )

        response = self.client.get(
            f"/manager/criteria/{criterion['id']}/edit?bureau_id=1",
        )
        self.assertEqual(response.status_code, 404)

    def test_applicant_and_availabilities_are_inserted_together(self) -> None:
        response = self.client.post('/applicants/new', data={
            'name': '新規 応募者',
            'email': 'new-applicant@example.invalid',
            'bureau_id': '1',
            'remark': 'テスト応募',
            'availability_ids': ['1', '2'],
        })
        self.assertEqual(response.status_code, 302)
        connection = self.connect()
        applicant = connection.execute(
            'SELECT id FROM applicants WHERE email = ?',
            ('new-applicant@example.invalid',),
        ).fetchone()
        self.assertIsNotNone(applicant)
        count = connection.execute(
            '''SELECT COUNT(*) FROM applicant_availabilities
               WHERE applicant_id = ?''', (applicant['id'],)
        ).fetchone()[0]
        self.assertEqual(count, 2)
        connection.close()

    def test_cross_bureau_availability_is_rejected(self) -> None:
        response = self.client.post('/applicants/new', data={
            'name': '不正 応募者',
            'email': 'invalid-applicant@example.invalid',
            'bureau_id': '1',
            'remark': '',
            'availability_ids': ['4'],
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('希望局に属さない面接枠'.encode(), response.data)
        connection = self.connect()
        count = connection.execute(
            'SELECT COUNT(*) FROM applicants WHERE email = ?',
            ('invalid-applicant@example.invalid',),
        ).fetchone()[0]
        self.assertEqual(count, 0)
        connection.close()

    def test_double_booking_is_rejected(self) -> None:
        response = self.client.post(
            '/applicants/103/schedule',
            data={'bureau_schedule_id': '1'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('error=', response.headers['Location'])
        connection = self.connect()
        confirmed = connection.execute(
            '''SELECT confirmed_bureau_schedule_id FROM applicants
               WHERE id = 103'''
        ).fetchone()[0]
        self.assertEqual(confirmed, 3)
        connection.close()

    def test_schedule_is_locked_after_scoring(self) -> None:
        response = self.client.post(
            '/applicants/101/schedule',
            data={'bureau_schedule_id': ''},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('error=', response.headers['Location'])
        connection = self.connect()
        confirmed = connection.execute(
            '''SELECT confirmed_bureau_schedule_id FROM applicants
               WHERE id = 101'''
        ).fetchone()[0]
        self.assertEqual(confirmed, 1)
        connection.close()

    def test_database_rejects_overlapping_slot(self) -> None:
        connection = self.connect()
        connection.execute(
            '''INSERT INTO schedules (id, start_at, end_at)
               VALUES (99, '2026-07-10 12:50:00', '2026-07-10 13:10:00')'''
        )
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    '''INSERT INTO bureau_schedules (bureau_id, schedule_id)
                       VALUES (1, 99)'''
                )
        finally:
            connection.close()

    def test_database_rejects_cross_bureau_score(self) -> None:
        connection = self.connect()
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                '''INSERT INTO scores
                   (applicant_id, interviewer_id, criterion_id, score)
                   VALUES (101, 3, 21, 5)'''
            )
        connection.close()

    def test_invalid_score_rolls_back_all_items(self) -> None:
        response = self.client.post(
            '/interviewers/1/applicants/101/scores',
            data={'score_1': '10', 'score_2': '0'},
        )
        self.assertEqual(response.status_code, 200)
        connection = self.connect()
        scores = connection.execute(
            '''SELECT criterion_id, score FROM scores
               WHERE applicant_id = 101 AND interviewer_id = 1
               ORDER BY criterion_id'''
        ).fetchall()
        saved_scores = [
            (row['criterion_id'], row['score']) for row in scores
        ]
        self.assertEqual(saved_scores, [(1, 9), (2, 8)])
        connection.close()

    def test_normalized_ranking_is_calculated(self) -> None:
        with app_module.app.app_context():
            bureau, rows = app_module.calculate_rankings(
                app_module.get_db(), 1,
            )
            self.assertEqual(bureau['name'], 'IT局')
            self.assertEqual(
                [row['applicant']['applicant_id'] for row in rows],
                [101, 102, 103],
            )
            self.assertAlmostEqual(
                rows[0]['normalized_score'], 55.0, places=2)
            self.assertEqual(rows[0]['candidate_status'], 'candidate')
            self.assertEqual(rows[1]['candidate_status'], 'candidate')
            self.assertEqual(rows[2]['candidate_status'], 'incomplete')


if __name__ == '__main__':
    unittest.main()
