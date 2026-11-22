// Histogram bin explorer. DATA[i] = {title, unit, note, values}; bins = current bin count.
var counts = [], ds = 0, bins = CFG.start, sturgesK = 0, fdK = 0, lo = 0, hi = 1, sorted = [];
function fld(n) { return this.getField(n); }
function vis(n, on) { fld(n).display = on ? display.visible : display.hidden; }
// r = [left, bottom, right, top] in page points. field.rect takes Acrobat's order [left, top, right, bottom], in
// whole points: Edge does not draw a field moved to fractional coordinates.
function place(n, r) {
  var f = fld(n), R = Math.round;
  f.display = display.hidden; f.rect = [R(r[0]), R(r[3]), R(r[2]), R(r[1])]; f.display = display.visible;
}
function quantile(s, q) {
  var p = (s.length - 1) * q, i = Math.floor(p), j = Math.min(i + 1, s.length - 1);
  return s[i] + (s[j] - s[i]) * (p - i);
}
function clampK(k) { return Math.max(CFG.KMIN, Math.min(CFG.KMAX, k)); }
function fmt(v) {
  var a = Math.abs(v);
  return a >= 100 ? String(Math.round(v)) : a >= 10 ? v.toFixed(1) : v.toFixed(2);
}
function kx(k) { return CFG.TX + (k - CFG.KMIN) * CFG.STEP; }
function setData(i) {
  ds = i;
  var d = DATA[i];
  sorted = d.values.slice().sort(function (a, b) { return a - b; });
  lo = sorted[0]; hi = sorted[sorted.length - 1];
  var n = sorted.length, iqr = quantile(sorted, 0.75) - quantile(sorted, 0.25);
  sturgesK = clampK(Math.ceil(Math.log(n) / Math.LN2) + 1);
  fdK = iqr > 0 ? clampK(Math.ceil((hi - lo) / (2 * iqr / Math.pow(n, 1 / 3)))) : CFG.KMAX;
  for (var j = 0; j < DATA.length; j++) { vis("dsSel" + j, j == i); vis("dsBg" + j, j != i); }
  fld("title").value = d.title + " (n = " + n + ")";
  fld("note").value = d.note;
  fld("xmin").value = fmt(lo) + " " + d.unit;
  fld("xmax").value = fmt(hi) + " " + d.unit;
  fld("lS").value = "Sturges: " + sturgesK + " bins";
  fld("lF").value = "Freedman-Diaconis: " + fdK + " bins" + (fdK == CFG.KMAX ? " (or more)" : "");
  place("mS", [kx(sturgesK) - 1.5, CFG.TY + 3, kx(sturgesK) + 1.5, CFG.TY + 12]);
  place("mF", [kx(fdK) - 1.5, CFG.TY - 12, kx(fdK) + 1.5, CFG.TY - 3]);
  draw();
}
function setBins(k) {
  bins = clampK(k);
  draw();
}
var dragging = false;
function grab(k) { dragging = true; setBins(k); }       // mouse down on the track: the knob jumps here and follows
function follow(k) { if (dragging && k != bins) setBins(k); }
function drop() { dragging = false; }
function draw() {
  var k = bins, d = DATA[ds], c = [], i, maxc = 0;
  for (i = 0; i < k; i++) c.push(0);
  for (i = 0; i < sorted.length; i++) {
    var b = hi > lo ? Math.floor((sorted[i] - lo) / (hi - lo) * k) : 0;
    c[Math.min(k - 1, b)]++;
  }
  for (i = 0; i < k; i++) if (c[i] > maxc) maxc = c[i];
  counts = c;
  var bw = CFG.CW / k, gap = bw > 6 ? 1.5 : bw > 3 ? 0.6 : 0;
  for (i = 0; i < CFG.KMAX; i++) {
    if (i < k && c[i] > 0) {
      var h = c[i] / maxc * CFG.CH, x = CFG.CX + i * bw + gap / 2;
      place("bar" + i, [x, CFG.CB, x + bw - gap, CFG.CB + h]);
    } else vis("bar" + i, false);
  }
  fld("ymax").value = String(maxc);
  fld("kTxt").value = String(k);
  fld("info").value = k + " bins, each " + fmt((hi - lo) / k) + " " + d.unit + " wide";
  var x = kx(k);
  place("knob", [x - 10, CFG.TY - 10, x + 10, CFG.TY + 10]);
}
setData(0);
