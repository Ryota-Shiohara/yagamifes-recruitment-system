BEGIN;

INSERT INTO bureaus (id, name, capacity) VALUES
    (1, 'IT局', 8),
    (2, '広報局', 14),
    (3, '屋外局', 16),
    (4, '室内局', 24),
    (5, 'ステージ局', 20),
    (6, '総務局', 18),
    (7, '渉外局', 10),
    (8, '装飾局', 14);

INSERT INTO interviewers (id, name, bureau_id, role) VALUES
    (1, '面接官 零一', 1, 'chief'),
    (2, '面接官 零二', 1, 'interviewer'),
    (3, '面接官 零三', 2, 'chief'),
    (4, '面接官 零四', 2, 'interviewer'),
    (5, '面接官 零五', 3, 'chief'),
    (6, '面接官 零六', 3, 'interviewer'),
    (7, '面接官 零七', 4, 'chief'),
    (8, '面接官 零八', 4, 'interviewer'),
    (9, '面接官 零九', 5, 'chief'),
    (10, '面接官 一〇', 5, 'interviewer'),
    (11, '面接官 一一', 6, 'chief'),
    (12, '面接官 一二', 6, 'interviewer'),
    (13, '面接官 一三', 7, 'chief'),
    (14, '面接官 一四', 7, 'interviewer'),
    (15, '面接官 一五', 8, 'chief'),
    (16, '面接官 一六', 8, 'interviewer');

INSERT INTO criteria (id, name, description, bureau_id) VALUES
    (1, '技術的意欲', 'プログラミングやIT技術への興味・学習意欲', 1),
    (2, '協調性', 'チーム開発や共同作業を円滑に進められるか', 1),
    (3, '発信力・企画力', 'SNS発信やデザイン、広報企画への関心・センス', 2),
    (4, 'コミュニケーション能力', '外部や他局との情報伝達がスムーズに行えるか', 2),
    (5, '体力・積極性', '屋外での設営やイベント進行における行動力と元気の良さ', 3),
    (6, '子ども対応力', '地域の子どもたちや来場者と明るく接することができるか', 3),
    (7, '対応力・柔軟性', '雨天時などの急な変更や、様々な企画調整に対応できるか', 4),
    (8, '丁寧さ', '学内施設の使用申請や、安全管理を丁寧に行えるか', 4),
    (9, '熱意・コミット度', '矢上祭の華であるステージ運営に情熱を注げるか', 5),
    (10, 'リーダーシップ', '出演者やスタッフを引っ張る積極性があるか', 5),
    (11, '計画性・責任感', '縁の下の力持ちとして、コツコツとタスクをこなす責任感', 6),
    (12, '事務処理適性', '予算管理や資料作成に対する適性・丁寧さ', 6),
    (13, '対人コミュニケーション力', '協賛企業への熱意ある提案や、礼儀正しい交渉ができるか', 7),
    (14, 'タフネス・粘り強さ', '目標額達成に向けて諦めずにアプローチを続けられるか', 7),
    (15, 'クリエイティビティ', '看板やアーチなどの制作に対する想像力・美術的興味', 8),
    (16, '作業継続力', '地道な制作作業に飽きずに取り組める集中力', 8);

INSERT INTO schedules (id, start_at, end_at) VALUES
    (1, '2026-07-10 13:00:00', '2026-07-10 13:30:00'),
    (2, '2026-07-10 13:40:00', '2026-07-10 14:10:00'),
    (3, '2026-07-10 14:20:00', '2026-07-10 14:50:00'),
    (4, '2026-07-11 10:00:00', '2026-07-11 10:30:00'),
    (5, '2026-07-11 10:40:00', '2026-07-11 11:10:00'),
    (6, '2026-07-11 11:20:00', '2026-07-11 11:50:00'),
    (7, '2026-07-12 15:00:00', '2026-07-12 15:30:00'),
    (8, '2026-07-12 15:40:00', '2026-07-12 16:10:00');

INSERT INTO bureau_schedules (id, bureau_id, schedule_id) VALUES
    (1, 1, 1), (2, 1, 2), (3, 1, 3),
    (4, 2, 2), (5, 2, 3), (6, 2, 4),
    (7, 3, 3), (8, 3, 4), (9, 3, 5),
    (10, 4, 4), (11, 4, 5), (12, 4, 6),
    (13, 5, 5), (14, 5, 6), (15, 5, 7),
    (16, 6, 6), (17, 6, 7), (18, 6, 8),
    (19, 7, 1), (20, 7, 2), (21, 7, 8),
    (22, 8, 1), (23, 8, 7), (24, 8, 8);

INSERT INTO applicants (id, name, email, bureau_id, remark, decision) VALUES
    (101, '志望者 零一', 'applicant01@example.com', 1, 'プログラミング経験あり、即戦力', 'accepted'),
    (102, '志望者 零二', 'applicant02@example.com', 1, 'Webデザインに興味ありとのこと', NULL),
    (103, '志望者 零三', 'applicant03@example.com', 1, '面接予定、遅刻なきよう連絡済', NULL),
    (201, '志望者 零四', 'applicant04@example.com', 2, 'SNS運用経験あり、明るくハキハキしている', 'accepted'),
    (202, '志望者 零五', 'applicant05@example.com', 2, '他サークルとの兼ね合いにより辞退', 'withdrawn'),
    (301, '志望者 零六', 'applicant06@example.com', 3, '高校時代サッカー部、体力に自信あり', 'accepted'),
    (302, '志望者 零七', 'applicant07@example.com', 3, '志望動機がやや薄かったため今回は見送り', 'rejected'),
    (401, '志望者 零八', 'applicant08@example.com', 4, '真面目で几帳面な印象、調整役に向いている', NULL),
    (402, '志望者 零九', 'applicant09@example.com', 4, '体育会系、スケジュール通り案内中', NULL),
    (501, '志望者 一〇', 'applicant10@example.com', 5, '文化祭でのステージ責任者経験あり、熱意十分', 'accepted'),
    (502, '志望者 一一', 'applicant11@example.com', 5, '少し緊張していたが、やりたい演出が明確', NULL),
    (601, '志望者 一二', 'applicant12@example.com', 6, 'エクセルが少し使える、コツコツ作業が得意とのこと', 'accepted'),
    (701, '志望者 一三', 'applicant13@example.com', 7, '言葉遣いが非常に丁寧で、交渉能力が高そう', NULL),
    (801, '志望者 一四', 'applicant14@example.com', 8, '美術部出身、大きな絵を描くのが好き', 'accepted');

INSERT INTO applicant_availabilities (applicant_id, bureau_schedule_id) VALUES
    (101, 1), (101, 2), (101, 3),
    (102, 1), (102, 2), (102, 3),
    (103, 1), (103, 2), (103, 3),
    (201, 4), (201, 5), (201, 6),
    (202, 4), (202, 5), (202, 6),
    (301, 7), (301, 8), (301, 9),
    (302, 7), (302, 8), (302, 9),
    (401, 10), (401, 11), (401, 12),
    (402, 10), (402, 11), (402, 12),
    (501, 13), (501, 14), (501, 15),
    (502, 13), (502, 14), (502, 15),
    (601, 16), (601, 17), (601, 18),
    (701, 19), (701, 20), (701, 21),
    (801, 22), (801, 23), (801, 24);

UPDATE applicants SET confirmed_bureau_schedule_id = 1 WHERE id = 101;
UPDATE applicants SET confirmed_bureau_schedule_id = 2 WHERE id = 102;
UPDATE applicants SET confirmed_bureau_schedule_id = 3 WHERE id = 103;
UPDATE applicants SET confirmed_bureau_schedule_id = 4 WHERE id = 201;
UPDATE applicants SET confirmed_bureau_schedule_id = 7 WHERE id = 301;
UPDATE applicants SET confirmed_bureau_schedule_id = 8 WHERE id = 302;
UPDATE applicants SET confirmed_bureau_schedule_id = 10 WHERE id = 401;
UPDATE applicants SET confirmed_bureau_schedule_id = 11 WHERE id = 402;
UPDATE applicants SET confirmed_bureau_schedule_id = 13 WHERE id = 501;
UPDATE applicants SET confirmed_bureau_schedule_id = 14 WHERE id = 502;
UPDATE applicants SET confirmed_bureau_schedule_id = 17 WHERE id = 601;
UPDATE applicants SET confirmed_bureau_schedule_id = 21 WHERE id = 701;
UPDATE applicants SET confirmed_bureau_schedule_id = 24 WHERE id = 801;

INSERT INTO scores (applicant_id, interviewer_id, criterion_id, score) VALUES
    (101, 1, 1, 9), (101, 1, 2, 8),
    (101, 2, 1, 10), (101, 2, 2, 8),
    (102, 1, 1, 7), (102, 1, 2, 7),
    (102, 2, 1, 6), (102, 2, 2, 9),
    (201, 3, 3, 9), (201, 3, 4, 10),
    (201, 4, 3, 8), (201, 4, 4, 9),
    (301, 5, 5, 10), (301, 5, 6, 8),
    (301, 6, 5, 9), (301, 6, 6, 8),
    (302, 5, 5, 5), (302, 5, 6, 4),
    (302, 6, 5, 6), (302, 6, 6, 5),
    (401, 7, 7, 8), (401, 7, 8, 9),
    (401, 8, 7, 7), (401, 8, 8, 8),
    (501, 9, 9, 10), (501, 9, 10, 9),
    (501, 10, 9, 9), (501, 10, 10, 10),
    (502, 9, 9, 8), (502, 9, 10, 7),
    (502, 10, 9, 7), (502, 10, 10, 7),
    (601, 11, 11, 8), (601, 11, 12, 8),
    (601, 12, 11, 9), (601, 12, 12, 7),
    (701, 13, 13, 9), (701, 13, 14, 8),
    (701, 14, 13, 8), (701, 14, 14, 7),
    (801, 15, 15, 9), (801, 15, 16, 9),
    (801, 16, 15, 10), (801, 16, 16, 8);

COMMIT;
