---
title: שגיאות נפוצות ב-Git ובגיטהב - מה הן אומרות ואיך פותרים
topic: errors
language: he
---

# שגיאות נפוצות ב-Git ובגיטהב

קובץ זה מרכז הודעות שגיאה נפוצות, מה הן אומרות ואיך פותרים אותן. כל סעיף מתחיל בטקסט של ההודעה כפי שהיא מופיעה בטרמינל.

## הפקודה git לא מזוהה

הודעה: `'git' is not recognized as an internal or external command` או `git: command not found`.

המשמעות: Git לא מותקן, או שהטרמינל נפתח לפני ההתקנה.

פתרון: מתקינים את Git, **סוגרים ופותחים מחדש** את הטרמינל, ובודקים עם `git --version`.

## not a git repository

הודעה: `fatal: not a git repository (or any of the parent directories): .git`

המשמעות: הפקודה הורצה בתיקייה שאינה מאגר Git.

פתרון: עוברים לתיקיית הפרויקט עם `cd`. אם זה פרויקט חדש שעוד לא אותחל, מריצים `git init`.

## Please tell me who you are

הודעה: `Author identity unknown *** Please tell me who you are.`

המשמעות: לא הוגדרו שם ואימייל, ולכן אי אפשר לבצע commit.

פתרון:
```
git config --global user.name "השם שלך"
git config --global user.email "המייל שלך"
```
ואז מריצים שוב את `git commit`.

## nothing to commit

הודעה: `nothing to commit, working tree clean`

המשמעות: זו לא שגיאה. אין שינויים חדשים מאז ה-commit האחרון. אם שינית קבצים והם לא מופיעים, ייתכן שהם ברשימת `.gitignore`, או ששמרת אותם בתיקייה אחרת.

## src refspec main does not match any

הודעה: `error: src refspec main does not match any`

המשמעות: מנסים להעלות ענף בשם `main`, אבל עוד אין בו commit, או שהענף נקרא בשם אחר (למשל `master`).

פתרון: מוודאים שבוצע commit (`git commit -m "first commit"`), ומשנים את שם הענף ל-`main`:
```
git branch -M main
git push -u origin main
```

## remote origin already exists

הודעה: `error: remote origin already exists.`

המשמעות: התיקייה כבר מחוברת למאגר בגיטהב.

פתרון: בודקים לאיזה מאגר עם `git remote -v`. כדי להחליף לכתובת אחרת:
```
git remote set-url origin https://github.com/USER/REPO.git
```

## push נדחה: rejected / fetch first

הודעה: `! [rejected] main -> main (fetch first)` או `Updates were rejected because the remote contains work that you do not have locally`.

המשמעות: בגיטהב יש שינויים שאין במחשב, למשל README שנוצר באתר או עבודה של שותף.

פתרון: מושכים קודם ואז מעלים:
```
git pull
git push
```
אם מופיע קונפליקט, פותרים אותו (ראו בסעיף CONFLICT) ואז מעלים.

## refusing to merge unrelated histories

הודעה: `fatal: refusing to merge unrelated histories`

המשמעות: המאגר במחשב והמאגר בגיטהב נוצרו בנפרד, למשל פרויקט מקומי ומאגר שנוצר באתר עם README.

פתרון:
```
git pull origin main --allow-unrelated-histories
git push -u origin main
```

## no upstream branch

הודעה: `fatal: The current branch feature-x has no upstream branch.`

המשמעות: הענף הנוכחי עוד לא הועלה לגיטהב.

פתרון: מעלים אותו בפעם הראשונה עם `-u` (שם הענף כאן הוא דוגמה):
```
git push -u origin feature-x
```

## בעיות התחברות: Authentication failed

הודעה: `remote: Support for password authentication was removed` או `fatal: Authentication failed`.

המשמעות: גיטהב לא מקבל את סיסמת החשבון בשורת הפקודה.

פתרון: מתחברים דרך החלון של Git Credential Manager, או יוצרים טוקן גישה (Personal Access Token) בהגדרות גיטהב ומדביקים אותו במקום הסיסמה. ב-Windows, אם נשמר במחשב טוקן ישן: **Credential Manager** של Windows ← **Windows Credentials** ← מוחקים את הרשומה של `git:https://github.com`, ומנסים שוב.

## Permission denied (publickey)

הודעה: `git@github.com: Permission denied (publickey).`

המשמעות: מתחברים ב-SSH, אבל מפתח ה-SSH של המחשב לא נוסף לחשבון גיטהב.

פתרון: מוסיפים את המפתח הציבורי בגיטהב: **Settings** ← **SSH and GPG keys** ← **New SSH key**. לחלופין, עוברים לכתובת HTTPS:
```
git remote set-url origin https://github.com/USER/REPO.git
```

## Repository not found

הודעה: `remote: Repository not found.`

המשמעות: הכתובת שגויה, המאגר נמחק, או שאין לחשבון שמחובר במחשב הרשאה למאגר (למשל מאגר פרטי של מישהו אחר).

פתרון: בודקים את הכתובת עם `git remote -v` ומשווים לכתובת בדף המאגר. אם זה מאגר של מישהו אחר, צריך לבקש ממנו להוסיף אותך כשותף (Collaborator).

## CONFLICT - קונפליקט במיזוג

הודעה: `CONFLICT (content): Merge conflict in file.txt` ו-`Automatic merge failed; fix conflicts and then commit the result.`

המשמעות: אותן שורות שונו בשני מקומות, ו-Git לא יודע איזו גרסה לבחור.

פתרון:
1. פותחים את הקובץ שמופיע בהודעה. בתוכו יש סימנים כאלה:
```
<<<<<<< HEAD
הגרסה שלך
=======
הגרסה השנייה
>>>>>>> main
```
2. משאירים את הגרסה הנכונה (או משלבים בין השתיים), ומוחקים את שלוש שורות הסימון: `<<<<<<<`, `=======`, `>>>>>>>`.
3. שומרים את הקובץ ומסיימים:
```
git add .
git commit -m "resolve conflict"
git push
```
כדי לבטל את המיזוג ולחזור למצב שלפניו:
```
git merge --abort
```

## local changes would be overwritten

הודעה: `error: Your local changes to the following files would be overwritten by merge` (או `by checkout`).

המשמעות: יש שינויים שלא נשמרו ב-commit, ו-`git pull` או מעבר ענף ידרסו אותם.

פתרון: שומרים את השינויים ב-commit לפני הפעולה, או מניחים אותם בצד ומחזירים אחרי:
```
git stash
git pull
git stash pop
```

## pathspec did not match any files

הודעה: `fatal: pathspec 'file.txt' did not match any files`

המשמעות: שם הקובץ בפקודה לא נכון, או שהפקודה הורצה בתיקייה אחרת.

פתרון: בודקים את השם ואת התיקייה עם `git status`. בשמות עם רווחים מקיפים את השם במירכאות.

## detached HEAD

הודעה: `You are in 'detached HEAD' state.`

המשמעות: עברת לצפייה ב-commit או בתגית מסוימת, ולא לענף. commits שיבוצעו כאן לא שייכים לאף ענף.

פתרון: חוזרים לענף הראשי:
```
git switch main
```

## קובץ גדול מדי

הודעה: `remote: error: File big.zip is 120.00 MB; this exceeds GitHub's file size limit of 100.00 MB`

המשמעות: גיטהב חוסם קבצים מעל 100MB.

פתרון: אם הקובץ נכנס ב-commit האחרון ועוד לא הועלה:
```
git rm --cached big.zip
git commit --amend -m "remove large file"
git push
```
ומוסיפים את הקובץ ל-`.gitignore`. אם הקובץ נכנס ב-commit מוקדם יותר, צריך לנקות את ההיסטוריה, וזו פעולה מתקדמת.

## קובץ סודי הועלה בטעות

אם קובץ `.env`, סיסמה או מפתח API הועלו לגיטהב, הצעד הראשון הוא **לבטל את המפתח או להחליף את הסיסמה** אצל השירות שהנפיק אותם, ורק אחר כך להסיר את הקובץ מהמעקב:
```
git rm --cached .env
git commit -m "stop tracking .env"
git push
```
ולהוסיף `.env` לקובץ `.gitignore`.

## אזהרת LF will be replaced by CRLF

הודעה: `warning: LF will be replaced by CRLF the next time Git touches it`

המשמעות: זו אזהרה ולא שגיאה. Windows ו-Mac/Linux מסמנים סוף שורה בצורה שונה, ו-Git ממיר ביניהן אוטומטית. אפשר להמשיך כרגיל.
