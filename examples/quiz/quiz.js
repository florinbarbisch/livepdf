// Quiz. States: "ask" (waiting for an answer), "answered" (feedback shown), "end" (score shown).
var cur = 0, score = 0, state = "ask";
function fld(n) { return this.getField(n); }
function vis(n, on) { fld(n).display = on ? display.visible : display.hidden; }
function rows(on) {
  for (var i = 0; i < 4; i++) {
    vis("aBg" + i, on); vis("aOk" + i, false); vis("aBad" + i, false); vis("aL" + i, on); vis("a" + i, on);
  }
}
function nextButton(caption) {
  vis("nextBg", caption != ""); fld("nextTxt").value = caption;
}
function showQuestion() {
  var q = QUESTIONS[cur];
  state = "ask";
  fld("q1").value = q.q[0]; fld("q2").value = q.q[1];
  rows(true);
  for (var i = 0; i < 4; i++) fld("a" + i).value = q.a[i];
  fld("fb").value = ""; fld("expl").value = "";
  fld("prog").value = "Question " + (cur + 1) + " of " + QUESTIONS.length;
  fld("score").value = "Score " + score;
  nextButton("");
}
function answer(i) {
  if (state != "ask") return;
  var q = QUESTIONS[cur];
  state = "answered";
  vis("aBg" + q.ok, false); vis("aOk" + q.ok, true);
  if (i == q.ok) { score++; fld("fb").value = "Correct!"; }
  else { vis("aBg" + i, false); vis("aBad" + i, true); fld("fb").value = "Not quite: it is " + "ABCD".charAt(q.ok) + "."; }
  fld("expl").value = q.why;
  fld("score").value = "Score " + score;
  nextButton(cur + 1 < QUESTIONS.length ? "Next question" : "See result");
}
function next() {
  if (state == "ask") return;              // the button is hidden while a question waits for an answer
  if (state == "end") { cur = 0; score = 0; showQuestion(); return; }
  cur++;
  if (cur < QUESTIONS.length) { showQuestion(); return; }
  state = "end";
  rows(false);
  var n = QUESTIONS.length;
  fld("q1").value = "You got " + score + " of " + n + " right.";
  fld("q2").value = score == n ? "Perfect!" : score >= n - 2 ? "Well done." : "Have another go?";
  fld("fb").value = ""; fld("expl").value = "";
  fld("prog").value = "Done";
  nextButton("Play again");
}
showQuestion();
