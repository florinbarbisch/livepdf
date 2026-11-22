// Guess r: game logic. Runs in the PDF viewer (Chrome/PDFium or Acrobat); build_game.py prepends CFG.
var N = CFG.N, PX = CFG.PX, PB = CFG.PB, PS = CFG.PS, M = CFG.M, DOT = CFG.DOT;
var CX = CFG.CX, CB = CFG.CB, CW = CFG.CW, CH = CFG.CH, CMAX = CFG.CMAX, NH = CFG.NHIST;
var cur = CFG.r0, done = false, over = false, errs = [];
var hearts = 3, coins = 0, streak = 0, best = 0;
function fld(n) { return this.getField(n); }
function vis(n, on) { var f = fld(n); if (f) f.display = on ? display.visible : display.hidden; }
function place(n, x, y, s) { var f = fld(n); f.display = display.hidden; f.rect = [x, y, x + s, y + s]; f.display = display.visible; }
function gauss() { var u = 1 - Math.random(), v = Math.random(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
function newPlot() {
  var t = Math.random(), xs, ys, r;
  do {
    xs = []; ys = [];
    for (var i = 0; i < N; i++) { var a = gauss(); xs.push(a); ys.push(t * a + Math.sqrt(1 - t * t) * gauss()); }
    var mx = 0, my = 0; for (i = 0; i < N; i++) { mx += xs[i]; my += ys[i]; } mx /= N; my /= N;
    var sxy = 0, sxx = 0, syy = 0;
    for (i = 0; i < N; i++) { var dx = xs[i] - mx, dy = ys[i] - my; sxy += dx * dy; sxx += dx * dx; syy += dy * dy; }
    r = sxy / Math.sqrt(sxx * syy);
  } while (r < 0);
  var lx = Math.min.apply(null, xs), hx = Math.max.apply(null, xs), ly = Math.min.apply(null, ys), hy = Math.max.apply(null, ys);
  for (i = 0; i < N; i++)
    place("d" + i, PX + M + (xs[i] - lx) / (hx - lx) * (PS - 2 * M) - DOT / 2, PB + M + (ys[i] - ly) / (hy - ly) * (PS - 2 * M) - DOT / 2, DOT);
  cur = Math.round(r * 100) / 100;
}
function f2(x) { return x.toFixed(2); }
function setRes(a, b, c) { fld("resTrue").value = a; fld("resRate").value = b; fld("resLine").value = c; }
function cyv(v) { v = Math.max(-CMAX, Math.min(CMAX, v)); return CB + (0.5 + v / (2 * CMAX)) * CH; }
function sgn(x) { return (x > 0 ? "+" : x < 0 ? "-" : "") + Math.abs(x).toFixed(2); }
// One handler for Check / Next plot / New game. What a click means is decided when the mouse button goes DOWN:
// clicking Check first commits the text field (which already checks the guess), and only then the button's own
// action runs, so the state at release time would wrongly say 'next plot'. Chrome may also repeat the release.
var lastMain = 0, pressState = -1, pressAt = 0;
function stateNow() { return over ? 2 : done ? 1 : 0; }
function press() { pressState = stateNow(); pressAt = new Date().getTime(); }
function main() {
  var now = new Date().getTime();
  var st = (pressState >= 0 && now - pressAt < 3000) ? pressState : stateNow();
  pressState = -1;
  if (now - lastMain < 300) return;
  lastMain = now;
  if (st == 2) newGame(); else if (st == 1) nextPlot(); else check(fld("guess").valueAsString);
}
function quart(a, q) { var s = a.slice().sort(function (x, y) { return x - y; }), p = (s.length - 1) * q, i = Math.floor(p);
  return i + 1 < s.length ? s[i] + (s[i + 1] - s[i]) * (p - i) : s[i]; }
function drawHistory() {
  var n = Math.min(errs.length, NH), off = errs.length - n, sum = 0, sabs = 0, i;
  for (i = 0; i < errs.length; i++) { sum += errs[i]; sabs += Math.abs(errs[i]); }
  for (i = 0; i < NH; i++) {
    if (i < n) place("h" + i, CX + (i + 0.5) * CW / NH - 7, cyv(errs[off + i]) - 7, 14); else vis("h" + i, false);
  }
  if (errs.length == 0) { vis("meanbar", false); vis("band", false); fld("stats").value = "no rounds yet"; return; }
  var my = cyv(sum / errs.length);
  var q1 = cyv(quart(errs, 0.25)), q3 = cyv(quart(errs, 0.75)), bd = fld("band");
  bd.display = display.hidden; bd.rect = [CX + 0.5, Math.min(q1, q3) - 1, CX + CW - 0.5, Math.max(q1, q3) + 1]; bd.display = display.visible;
  var b = fld("meanbar"); b.display = display.hidden; b.rect = [CX, my - 0.8, CX + CW, my + 0.8]; b.display = display.visible;
  fld("stats").value = errs.length + (errs.length == 1 ? " round" : " rounds") + "  ·  mean |error| " + f2(sabs / errs.length) + "  ·  bias " + sgn(sum / errs.length);
}
function drawHud() {
  for (var i = 0; i < 5; i++) vis("hf" + i, i < hearts);
  fld("coins").value = String(coins);
  fld("streak").value = "streak " + streak + (best > 0 ? "  (best " + best + ")" : "");
}
function check(raw) {
  if (done || over) return;
  var s = String(raw).replace(",", ".").replace(/\s/g, "");
  if (s == "" || s == "0.") return;
  var g = Number(s);
  if (isNaN(g) || g < 0 || g > 1) { fld("warn").value = "Please type a number between 0 and 1, e.g. 0.6"; return; }
  fld("warn").value = "";
  var res = Math.round((g - cur) * 100) / 100, e = Math.abs(res);
  var gain = e <= 0.02 ? 5 : e <= 0.05 ? 3 : e <= 0.10 ? 1 : 0, bonus = 0, rate;
  if (e <= 0.05) { streak++; bonus = streak - 1; if (streak > best) best = streak; } else streak = 0;
  coins += gain + bonus;
  if (e > 0.10) { hearts--; rate = (e <= 0.20 ? "Close" : "Not quite") + ", -1 heart"; }
  else if (e <= 0.02) { var up = hearts < 5; if (up) hearts++; rate = up ? "Perfect! +1 heart" : "Perfect!"; }
  else rate = e <= 0.05 ? "Excellent!" : "Very good";
  var line = "Guess " + f2(g) + "  ·  residual " + sgn(res) + "  ·  +" + (gain + bonus) + " coins" + (bonus > 0 ? " (streak +" + bonus + ")" : "");
  errs.push(res); drawHistory();
  if (hearts <= 0) {
    over = true;
    setRes("r = " + f2(cur), "Game over", "Final: " + coins + " coins in " + errs.length + " rounds, best streak " + best);
    vis("btnCheck", false); vis("btnNew", true);
  } else {
    setRes("r = " + f2(cur), rate, line);
    vis("btnCheck", false); vis("btnNext", true);
  }
  drawHud();
  done = true;
}
function nextPlot() {
  newPlot();
  setRes("", "", ""); fld("warn").value = "";
  fld("guess").value = "0.";
  vis("btnNext", false); vis("btnNew", false); vis("btnCheck", true);
  done = false;
  try { fld("guess").setFocus(); } catch (e) { }
}
function newGame() {
  hearts = 3; coins = 0; streak = 0; best = 0; over = false; errs = [];
  drawHistory(); drawHud(); nextPlot();
}
