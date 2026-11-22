// F1 slider: precision and recall sliders, animated bars for both, their plain average and F1.
// build.py prepends CFG = {P0, R0, start: {P, R, A, F}}.
var st = {P: CFG.start.P, R: CFG.start.R, A: CFG.start.A, F: CFG.start.F};   // what is drawn now
var tg = {P: CFG.start.P, R: CFG.start.R, A: CFG.start.A, F: CFG.start.F};   // where the bars are heading
var val = {P: CFG.P0, R: CFG.R0};
var timer = null;
var drag = null;   // which slider is being dragged, or null
// Drag and drop: mouse down on a slider track (or its knob) grabs it there, the zones' enter events follow the
// pointer while the button is held, mouse up drops it. Chrome sends mouse up to the pressed zone first.
function zDown(k, v) { drag = k; setVal(k, v); }
function zEnter(k, v) { if (drag == k) setVal(k, v); }
function zUp() { drag = null; }
function vis(n, on) { var f = this.getField(n); if (f) f.display = on ? display.visible : display.hidden; }
function draw(k, v) {
  var o = st[k];
  if (o > 0) vis("b" + k + "_" + o, false);
  if (v > 0) vis("b" + k + "_" + v, true);
  st[k] = v;
  this.getField("v" + k).value = v + " %";
}
function tick() {
  var moving = false;
  for (var k in st) {
    var d = tg[k] - st[k];
    if (d != 0) {
      var s = Math.max(1, Math.round(Math.abs(d) * 0.22));   // ease out: big steps first, small at the end
      draw(k, st[k] + (d > 0 ? s : -s));
      moving = true;
    }
  }
  if (!moving && timer) { app.clearInterval(timer); timer = null; }
}
function setVal(k, v) {
  if (val[k] == v) return;
  vis("k" + k + "_" + val[k], false); vis("k" + k + "_" + v, true);
  val[k] = v;
  var p = val.P, r = val.R, a = (p + r) / 2, f1 = (p + r) > 0 ? 2 * p * r / (p + r) : 0;
  tg.P = p; tg.R = r; tg.A = Math.round(a); tg.F = Math.round(f1);
  var gap = a - f1;
  this.getField("msg").value = gap < 0.05 ? "Precision and recall are equal: F1 equals the plain average."
    : "F1 is " + gap.toFixed(1) + " points below the plain average: the weaker side pulls it down.";
  if (!timer) timer = app.setInterval("tick()", 16);
}
for (var k in st) this.getField("v" + k).value = st[k] + " %";
this.getField("msg").value = "F1 is " + ((val.P + val.R) / 2 - 2 * val.P * val.R / (val.P + val.R)).toFixed(1) + " points below the plain average: the weaker side pulls it down.";
