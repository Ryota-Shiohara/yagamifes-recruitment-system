# 委員会新規局員採用システム 設計

## ER構造

~~~mermaid
erDiagram
    bureaus ||--o{ interviewers : "所属"
    bureaus ||--o{ criteria : "所有"
    bureaus ||--o{ applicants : "第一希望"
    bureaus ||--o{ bureau_schedules : "利用可能"
    schedules ||--o{ bureau_schedules : "時間"
    applicants ||--o{ applicant_availabilities : "希望"
    bureau_schedules ||--o{ applicant_availabilities : "希望される"
    bureau_schedules o|--o| applicants : "確定面接枠"
    applicants ||--o{ scores : "評価対象"
    interviewers ||--o{ scores : "評価者"
    criteria ||--o{ scores : "評価項目"
~~~

面接官と面接枠の割り当ては保存しません。同じ局で同時に複数面接を行わないため、bureau_schedules の「局＋時間」が一つの面接枠を表します。面接官は同じ局の面接確定済み応募者を評価できます。

## 課題3データとの対応

seed.sql は、課題3で作成した insert_data.sql の架空データを基にしている。局8件、面接官16件、評価項目16件、共通時間帯58件、局別面接枠424件、応募者94件、希望枠442件、評価156件を保持している。2026-07-14〜2026-07-18の各局50枠を追加し、面接未確定・未評価・採否未決定の応募者を混在させて、実運用の途中段階を再現している。

課題3からの主な拡張は、応募者の複数希望を保存する applicant_availabilities、局別面接枠を一意に参照する bureau_schedules.id、確定枠の二重予約を防ぐUNIQUE制約、局・評価者・評価項目の一致を検証するトリガーである。課題3の Accepted / Pending / Withdrawn / Rejected は、採用・未決定・辞退・不採用へ対応付けた。

## 候補キーと正規化

| テーブル | 候補キー |
| --- | --- |
| bureaus | {id}, {name} |
| interviewers | {id} |
| criteria | {id}, {bureau_id, name} |
| schedules | {id}, {start_at, end_at} |
| bureau_schedules | {id}, {bureau_id, schedule_id} |
| applicants | {id}, {email} |
| applicant_availabilities | {applicant_id, bureau_schedule_id} |
| scores | {applicant_id, interviewer_id, criterion_id} |

各表の非自明な関数従属性の左辺は候補キーです。中間テーブルには非キー属性がありません。したがって全表はBCNFであり、3NFでもあります。

scores には人工キーを設けません。応募者・評価者・評価項目の組が評価を一意に定め、同じ組への再入力は ON CONFLICT ... DO UPDATE で更新します。

## 主要な整合性制約

- bureaus.capacity >= 0
- schedules.start_at < schedules.end_at
- scores.score BETWEEN 1 AND 10
- 一つの局と共通時間帯の組は一意
- 一つの局別面接枠を確定できる応募者は一人
- 応募者のメールアドレスは大文字小文字を区別せず一意
- 応募者の希望枠と確定枠は応募先局に属する
- 確定枠は、応募者が希望した枠の一つ
- 評価入力後は確定面接枠を変更できない
- 評価者、応募者、評価項目は同じ局に属する
- 同じ局の面接枠は時間的にも重複しない

最後の4項目は複数表にまたがるため、アプリの事前検証に加えてSQLiteトリガーでも拒否します。

## VIEW

applicant_overview は応募者、局、確定面接枠、共通時間帯を結合します。日程未確定の応募者も残すため、面接枠と時間帯には LEFT JOIN を使用します。

VIEW自体には局を固定する WHERE や ORDER BY を含めません。応募者一覧側のSELECTで、局・氏名・日程確定状況・採否を可変条件として指定します。

## 評価者補正

評価者 i、評価項目 c、応募者 a の素点を x(a,i,c) とします。

1. n(i,c) = COUNT(x)
2. μ(i,c) = AVG(x)
3. σ(i,c) = sqrt(AVG(x²) - μ(i,c)²)
4. z(a,i,c) = (x(a,i,c) - μ(i,c)) / σ(i,c)
5. T(a,i,c) = 50 + 10z(a,i,c)
6. 応募者の補正後総合得点は、全 T(a,i,c) の平均

COUNT(score)、AVG(score)、AVG(score * score) はSQLで集約します。平方根とT得点はPythonで計算します。補正後得点は派生値なのでDBには保存しません。

- n < 2: 補正用標本不足として順位を確定しない
- σ = 0: 全評価に差がないため z = 0, T = 50
- 評価者2人未満または全評価項目がそろわない: 評価不足として順位を確定しない
- 採用人数の境界で同点: 自動確定せず「境界同点」と表示

## 画面とSQL操作

| 画面・処理 | 主なSQL・技法 |
| --- | --- |
| 応募登録 | INSERT applicants、INSERT applicant_availabilities、トランザクション |
| 応募者一覧 | applicant_overview、可変 WHERE、パラメータ化 |
| 応募者詳細 | 複数表 JOIN、評価件数 COUNT |
| 応募情報編集 | UPDATE、希望枠の INSERT / DELETE、トランザクション |
| 面接割り当てボード | 応募者・希望枠・予約状況の SELECT、確定枠の UPDATE、UNIQUE、希望枠存在確認 |
| 局別面接枠 | schedules / bureau_schedules の INSERT、UPDATE / DELETE、重複時間検証 |
| 採用基準管理 | criteria の局別 SELECT、INSERT、UPDATE、局内一意制約 |
| 評価入力 | 複合主キー、UPSERT、全項目トランザクション |
| ランキング | AVG、COUNT、GROUP BY、複数表 JOIN、z得点 |
| 採否決定 | UPDATE applicants.decision |

すべてのユーザー入力はSQLプレースホルダーで渡します。更新・削除はPOSTだけで行い、Jinja2の自動エスケープを維持します。
