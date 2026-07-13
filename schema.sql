PRAGMA foreign_keys = OFF;

DROP VIEW IF EXISTS applicant_overview;
DROP TRIGGER IF EXISTS bureau_schedule_no_overlap_insert;
DROP TRIGGER IF EXISTS bureau_schedule_no_overlap_update;
DROP TRIGGER IF EXISTS availability_same_bureau_insert;
DROP TRIGGER IF EXISTS availability_same_bureau_update;
DROP TRIGGER IF EXISTS availability_not_confirmed_delete;
DROP TRIGGER IF EXISTS applicant_confirmed_schedule_update;
DROP TRIGGER IF EXISTS applicant_schedule_locked_after_score;
DROP TRIGGER IF EXISTS score_same_bureau_insert;
DROP TRIGGER IF EXISTS score_same_bureau_update;
DROP TABLE IF EXISTS scores;
DROP TABLE IF EXISTS applicant_availabilities;
DROP TABLE IF EXISTS applicants;
DROP TABLE IF EXISTS bureau_schedules;
DROP TABLE IF EXISTS schedules;
DROP TABLE IF EXISTS criteria;
DROP TABLE IF EXISTS interviewers;
DROP TABLE IF EXISTS bureaus;
DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS items;
DROP TABLE IF EXISTS departments;
DROP TABLE IF EXISTS suppliers;
DROP TABLE IF EXISTS stores;
DROP TABLE IF EXISTS employees;

PRAGMA foreign_keys = ON;

CREATE TABLE bureaus (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    capacity INTEGER NOT NULL CHECK (capacity >= 0)
);

CREATE TABLE interviewers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    bureau_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('chief', 'interviewer')),
    FOREIGN KEY (bureau_id) REFERENCES bureaus(id)
);

CREATE TABLE criteria (
    id INTEGER PRIMARY KEY,
    bureau_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    UNIQUE (bureau_id, name),
    FOREIGN KEY (bureau_id) REFERENCES bureaus(id)
);

CREATE TABLE schedules (
    id INTEGER PRIMARY KEY,
    start_at DATETIME NOT NULL,
    end_at DATETIME NOT NULL,
    CHECK (start_at < end_at),
    UNIQUE (start_at, end_at)
);

CREATE TABLE bureau_schedules (
    id INTEGER PRIMARY KEY,
    bureau_id INTEGER NOT NULL,
    schedule_id INTEGER NOT NULL,
    UNIQUE (bureau_id, schedule_id),
    FOREIGN KEY (bureau_id) REFERENCES bureaus(id),
    FOREIGN KEY (schedule_id) REFERENCES schedules(id)
);

CREATE TABLE applicants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    bureau_id INTEGER NOT NULL,
    remark TEXT NOT NULL DEFAULT '',
    confirmed_bureau_schedule_id INTEGER UNIQUE,
    decision TEXT CHECK (
        decision IN ('accepted', 'rejected', 'waitlisted', 'withdrawn')
        OR decision IS NULL
    ),
    FOREIGN KEY (bureau_id) REFERENCES bureaus(id),
    FOREIGN KEY (confirmed_bureau_schedule_id)
        REFERENCES bureau_schedules(id)
);

CREATE TABLE applicant_availabilities (
    applicant_id INTEGER NOT NULL,
    bureau_schedule_id INTEGER NOT NULL,
    PRIMARY KEY (applicant_id, bureau_schedule_id),
    FOREIGN KEY (applicant_id)
        REFERENCES applicants(id) ON DELETE CASCADE,
    FOREIGN KEY (bureau_schedule_id)
        REFERENCES bureau_schedules(id)
);

CREATE TABLE scores (
    applicant_id INTEGER NOT NULL,
    interviewer_id INTEGER NOT NULL,
    criterion_id INTEGER NOT NULL,
    score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 10),
    PRIMARY KEY (applicant_id, interviewer_id, criterion_id),
    FOREIGN KEY (applicant_id)
        REFERENCES applicants(id) ON DELETE CASCADE,
    FOREIGN KEY (interviewer_id) REFERENCES interviewers(id),
    FOREIGN KEY (criterion_id) REFERENCES criteria(id)
);

CREATE TRIGGER bureau_schedule_no_overlap_insert
BEFORE INSERT ON bureau_schedules
WHEN EXISTS (
    SELECT 1
    FROM bureau_schedules AS existing
    JOIN schedules AS existing_schedule
        ON existing_schedule.id = existing.schedule_id
    JOIN schedules AS new_schedule
        ON new_schedule.id = NEW.schedule_id
    WHERE existing.bureau_id = NEW.bureau_id
      AND new_schedule.start_at < existing_schedule.end_at
      AND new_schedule.end_at > existing_schedule.start_at
)
BEGIN
    SELECT RAISE(ABORT, 'bureau schedule overlaps an existing slot');
END;

CREATE TRIGGER bureau_schedule_no_overlap_update
BEFORE UPDATE OF bureau_id, schedule_id ON bureau_schedules
WHEN EXISTS (
    SELECT 1
    FROM bureau_schedules AS existing
    JOIN schedules AS existing_schedule
        ON existing_schedule.id = existing.schedule_id
    JOIN schedules AS new_schedule
        ON new_schedule.id = NEW.schedule_id
    WHERE existing.bureau_id = NEW.bureau_id
      AND existing.id <> OLD.id
      AND new_schedule.start_at < existing_schedule.end_at
      AND new_schedule.end_at > existing_schedule.start_at
)
BEGIN
    SELECT RAISE(ABORT, 'bureau schedule overlaps an existing slot');
END;

CREATE TRIGGER availability_same_bureau_insert
BEFORE INSERT ON applicant_availabilities
WHEN NOT EXISTS (
    SELECT 1
    FROM applicants AS applicant
    JOIN bureau_schedules AS bureau_schedule
      ON bureau_schedule.id = NEW.bureau_schedule_id
    WHERE applicant.id = NEW.applicant_id
      AND applicant.bureau_id = bureau_schedule.bureau_id
)
BEGIN
    SELECT RAISE(ABORT, 'availability must belong to the applicant bureau');
END;

CREATE TRIGGER availability_same_bureau_update
BEFORE UPDATE ON applicant_availabilities
WHEN NOT EXISTS (
    SELECT 1
    FROM applicants AS applicant
    JOIN bureau_schedules AS bureau_schedule
      ON bureau_schedule.id = NEW.bureau_schedule_id
    WHERE applicant.id = NEW.applicant_id
      AND applicant.bureau_id = bureau_schedule.bureau_id
)
BEGIN
    SELECT RAISE(ABORT, 'availability must belong to the applicant bureau');
END;

CREATE TRIGGER availability_not_confirmed_delete
BEFORE DELETE ON applicant_availabilities
WHEN EXISTS (
    SELECT 1
    FROM applicants
    WHERE id = OLD.applicant_id
      AND confirmed_bureau_schedule_id = OLD.bureau_schedule_id
)
BEGIN
    SELECT RAISE(ABORT, 'confirmed schedule cannot be removed from availability');
END;

CREATE TRIGGER applicant_confirmed_schedule_update
BEFORE UPDATE OF confirmed_bureau_schedule_id ON applicants
WHEN NEW.confirmed_bureau_schedule_id IS NOT NULL
 AND NOT EXISTS (
    SELECT 1
    FROM applicant_availabilities AS availability
    JOIN bureau_schedules AS bureau_schedule
      ON bureau_schedule.id = availability.bureau_schedule_id
    WHERE availability.applicant_id = NEW.id
      AND availability.bureau_schedule_id = NEW.confirmed_bureau_schedule_id
      AND bureau_schedule.bureau_id = NEW.bureau_id
)
BEGIN
    SELECT RAISE(ABORT, 'confirmed schedule must be an applicant availability');
END;

CREATE TRIGGER applicant_schedule_locked_after_score
BEFORE UPDATE OF confirmed_bureau_schedule_id ON applicants
WHEN OLD.confirmed_bureau_schedule_id IS NOT NEW.confirmed_bureau_schedule_id
 AND EXISTS (
    SELECT 1 FROM scores WHERE applicant_id = OLD.id
)
BEGIN
    SELECT RAISE(ABORT, 'confirmed schedule is locked after scoring');
END;

CREATE TRIGGER score_same_bureau_insert
BEFORE INSERT ON scores
WHEN NOT EXISTS (
    SELECT 1
    FROM applicants AS applicant
    JOIN interviewers AS interviewer
      ON interviewer.id = NEW.interviewer_id
     AND interviewer.bureau_id = applicant.bureau_id
    JOIN criteria AS criterion
      ON criterion.id = NEW.criterion_id
     AND criterion.bureau_id = applicant.bureau_id
    WHERE applicant.id = NEW.applicant_id
      AND applicant.confirmed_bureau_schedule_id IS NOT NULL
)
BEGIN
    SELECT RAISE(ABORT, 'score participants must belong to the same bureau');
END;

CREATE TRIGGER score_same_bureau_update
BEFORE UPDATE ON scores
WHEN NOT EXISTS (
    SELECT 1
    FROM applicants AS applicant
    JOIN interviewers AS interviewer
      ON interviewer.id = NEW.interviewer_id
     AND interviewer.bureau_id = applicant.bureau_id
    JOIN criteria AS criterion
      ON criterion.id = NEW.criterion_id
     AND criterion.bureau_id = applicant.bureau_id
    WHERE applicant.id = NEW.applicant_id
      AND applicant.confirmed_bureau_schedule_id IS NOT NULL
)
BEGIN
    SELECT RAISE(ABORT, 'score participants must belong to the same bureau');
END;

CREATE VIEW applicant_overview AS
SELECT
    applicant.id AS applicant_id,
    applicant.name AS applicant_name,
    applicant.email,
    applicant.bureau_id,
    bureau.name AS bureau_name,
    applicant.remark,
    applicant.confirmed_bureau_schedule_id,
    schedule.start_at,
    schedule.end_at,
    applicant.decision
FROM applicants AS applicant
JOIN bureaus AS bureau ON bureau.id = applicant.bureau_id
LEFT JOIN bureau_schedules AS bureau_schedule
  ON bureau_schedule.id = applicant.confirmed_bureau_schedule_id
LEFT JOIN schedules AS schedule ON schedule.id = bureau_schedule.schedule_id;
