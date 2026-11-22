// Memory. deck[i] = pair number (0..7) of card i, shown by its field sym<i>_<pair>; open = cards turned up this move; solved[i] = pair found.
var deck = [], solved = [], open = [], moves = 0, pairs = 0, startAt = 0, clock = null, back = null, best = null;
function fld(n) { return this.getField(n); }
function vis(n, on) { fld(n).display = on ? display.visible : display.hidden; }
function show(i, face) {               // face: "back", "face" or "done"
  vis("back" + i, face == "back"); vis("face" + i, face == "face"); vis("done" + i, face == "done");
  for (var p = 0; p < 8; p++) vis("sym" + i + "_" + p, face != "back" && p == deck[i]);
}
function shuffle() {
  deck = [];
  for (var p = 0; p < 8; p++) { deck.push(p); deck.push(p); }
  for (var i = deck.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)), t = deck[i]; deck[i] = deck[j]; deck[j] = t; }
}
function tickClock() { fld("time").value = Math.floor((new Date().getTime() - startAt) / 1000) + " s"; }
function stopClock() { if (clock) { app.clearInterval(clock); clock = null; } }
function newGame() {
  stopClock();
  if (back) { app.clearTimeOut(back); back = null; }
  shuffle();
  solved = []; open = []; moves = 0; pairs = 0; startAt = 0;
  for (var i = 0; i < 16; i++) {
    solved.push(false);
    show(i, "back");
  }
  fld("moves").value = "0"; fld("time").value = "0 s"; fld("msg").value = "";
}
function turnBack() {
  if (back) { app.clearTimeOut(back); back = null; }
  for (var k = 0; k < open.length; k++) show(open[k], "back");
  open = [];
}
function flip(i) {
  if (solved[i]) return;
  if (open.length == 2) turnBack();      // a wrong pair is still showing: turn it back now
  if (open.length == 1 && open[0] == i) return;
  if (startAt == 0) { startAt = new Date().getTime(); clock = app.setInterval("tickClock()", 1000); }
  show(i, "face");
  open.push(i);
  if (open.length < 2) return;
  moves++;
  fld("moves").value = String(moves);
  var a = open[0], b = open[1];
  if (deck[a] == deck[b]) {
    solved[a] = solved[b] = true;
    show(a, "done"); show(b, "done");
    open = [];
    pairs++;
    if (pairs == 8) won();
  } else {
    back = app.setTimeOut("turnBack()", 900);
  }
}
function won() {
  stopClock(); tickClock();
  var secs = Math.floor((new Date().getTime() - startAt) / 1000);
  var record = best === null || moves < best.moves || (moves == best.moves && secs < best.secs);
  if (record) { best = {moves: moves, secs: secs}; fld("best").value = moves + " moves, " + secs + " s"; }
  fld("msg").value = (record ? "New best! " : "Solved! ") + moves + " moves.";
}
newGame();
