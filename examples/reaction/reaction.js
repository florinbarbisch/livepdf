// Reaction test. States: idle -> wait (random delay) -> go -> shown -> wait ... ; a click while waiting is "too early".
var state = "idle", goAt = 0, timer = null, times = [], bestAvg = null;
function fld(n) { return this.getField(n); }
function pad(which, text, sub) {
  var names = ["padIdle", "padWait", "padGo", "padEarly"];
  for (var i = 0; i < names.length; i++) fld(names[i]).display = names[i] == which ? display.visible : display.hidden;
  fld("padText").value = text;
  fld("padSub").value = sub || "";
}
function now() { return new Date().getTime(); }
function startWait() {
  state = "wait";
  pad("padWait", "Wait for green ...", "");
  var ms = Math.round(CFG.minWait + Math.random() * (CFG.maxWait - CFG.minWait));
  timer = app.setTimeOut("goNow()", ms);
}
function goNow() {
  timer = null;
  if (state != "wait") return;
  state = "go";
  goAt = now();
  pad("padGo", "Click!", "");
}
function showTries() {
  for (var i = 0; i < CFG.tries; i++)
    fld("try" + i).value = (i + 1) + ".  " + (i < times.length ? times[i] + " ms" : "-");
  if (times.length == 0) { fld("avg").value = ""; return; }
  var s = 0;
  for (i = 0; i < times.length; i++) s += times[i];
  fld("avg").value = "average " + Math.round(s / times.length) + " ms";
}
function tap() {
  if (state == "go") {
    var t = now() - goAt;
    times.push(t);
    showTries();
    if (times.length >= CFG.tries) {
      var s = 0;
      for (var i = 0; i < times.length; i++) s += times[i];
      var avg = Math.round(s / times.length);
      var record = bestAvg === null || avg < bestAvg;
      if (record) { bestAvg = avg; fld("best").value = avg + " ms"; }
      state = "done";
      pad("padIdle", avg + " ms average", (record ? "New best! " : "") + "Click to start a new series.");
    } else {
      state = "shown";
      pad("padIdle", t + " ms", "Click for the next try (" + (times.length + 1) + " of " + CFG.tries + ").");
    }
  } else if (state == "wait") {
    if (timer) { app.clearTimeOut(timer); timer = null; }
    state = "early";
    pad("padEarly", "Too early!", "Wait for green. Click to try again; this try does not count.");
  } else {
    if (state == "done") { times = []; showTries(); }
    startWait();
  }
}
