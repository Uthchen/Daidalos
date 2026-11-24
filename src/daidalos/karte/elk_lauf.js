/*
  daidalos – ELK im Web Worker (A09b)

  Ersetzt das globale ELK von elk-api.js durch eine Hülle, bevor cytoscape-elk es übernimmt. Das
  Layout rechnet in einem Web Worker, die Seite friert also nie ein. Der Worker entsteht aus einem
  Blob des eingebetteten Quelltexts (<script type="text/plain" id="elk-worker">), weil file:// keine
  Worker-Datei laden darf. Ein Worker wird für alle Layouts wiederverwendet.

  Steuerung über window.daidalosElk (setzt karte.js):
    zeitgrenze      ms je Layout (Standard 5000); danach wird der Worker beendet
    beiAbbruch(g)   Rückruf bei Zeitgrenze oder fehlendem Worker, g = 'zeitgrenze' | 'kein-worker' | 'fehler'
    abbrechen()     beendet ein laufendes Layout (dessen Promise bleibt offen, nichts wird gesetzt)
    zaehler         abgebrochen, zeitgrenze, layouts (für die Browser-Probe)
    laeuft()        läuft gerade ein Layout?
    testHaengen(b)  Testhaken: der nächste Worker antwortet nie
*/
(function () {
  'use strict';
  const ElkApi = window.ELK;
  const quelle = document.getElementById('elk-worker').textContent;
  let url = null, haengeUrl = null;
  let elk = null;        // gemeinsame ELK-Instanz mit ihrem Worker
  let laufend = null;    // { uhr } des laufenden Layouts
  let haengen = false;

  function fabrik() {
    if (haengen) {
      if (!haengeUrl) haengeUrl = URL.createObjectURL(new Blob(['self.onmessage = function () {};'], { type: 'text/javascript' }));
      return new Worker(haengeUrl);
    }
    if (!url) url = URL.createObjectURL(new Blob([quelle], { type: 'text/javascript' }));
    return new Worker(url);
  }
  function verwerfen() {
    if (elk) { try { elk.terminateWorker(); } catch (e) { /* schon beendet */ } }
    elk = null;
  }
  function beenden() {
    if (!laufend) return false;
    steuerung.zaehler.abgebrochen++;
    clearTimeout(laufend.uhr);
    laufend = null;
    verwerfen();
    return true;
  }

  // Der Worker liefert eine Kopie des Graphen; cytoscape-elk liest die Lage aber aus seinem eigenen
  // Objekt. Daher wird das Ergebnis in den Ausgangsgraphen zurückgeschrieben (Felder mit gleicher
  // id bzw. gleichem Index).
  function uebertrage(ziel, von) {
    Object.keys(von).forEach(s => {
      const a = ziel[s], b = von[s];
      if (Array.isArray(a) && Array.isArray(b)) {
        const nachId = new Map();
        a.forEach(x => { if (x && typeof x === 'object' && x.id !== undefined) nachId.set(x.id, x); });
        b.forEach((x, i) => {
          if (!x || typeof x !== 'object') { a[i] = x; return; }
          const t = x.id !== undefined && nachId.has(x.id) ? nachId.get(x.id) : (a[i] && typeof a[i] === 'object' ? a[i] : null);
          if (t) uebertrage(t, x); else a.push(x);
        });
      } else if (a && b && typeof a === 'object' && typeof b === 'object' && !Array.isArray(a) && !Array.isArray(b)) {
        uebertrage(a, b);
      } else {
        ziel[s] = b;
      }
    });
  }

  const steuerung = window.daidalosElk = {
    zeitgrenze: 5000,
    beiAbbruch: null,
    abbrechen: beenden,
    laeuft: () => !!laufend,
    zaehler: { abgebrochen: 0, zeitgrenze: 0, layouts: 0 },
    letzterFehler: null,
    testHaengen(b) { haengen = !!b; verwerfen(); }
  };

  function melde(grund) {
    if (typeof steuerung.beiAbbruch === 'function') setTimeout(() => steuerung.beiAbbruch(grund), 0);
  }

  // Hülle mit der Schnittstelle, die cytoscape-elk nutzt: new ELK(), elk.layout(graph).
  function ElkImWorker() {}
  ElkImWorker.prototype.layout = function (graph, opt) {
    beenden();
    if (!elk) {
      try { elk = new ElkApi({ workerFactory: fabrik }); } catch (e) { elk = null; }
    }
    if (!elk) { melde('kein-worker'); return new Promise(() => {}); }
    const eigen = elk;
    const lauf = {};
    laufend = lauf;
    steuerung.zaehler.layouts++;
    lauf.uhr = setTimeout(() => {
      if (laufend !== lauf) return;
      clearTimeout(lauf.uhr);
      laufend = null;
      verwerfen();
      steuerung.zaehler.zeitgrenze++;
      melde('zeitgrenze');
    }, steuerung.zeitgrenze);
    // cytoscape-elk hängt Cytoscape-Elemente an (_cyEle); die lassen sich nicht an einen Worker
    // schicken. Gesendet wird eine Kopie ohne Schlüssel mit „_“.
    const rein = JSON.parse(JSON.stringify(graph, (s, v) => (s.charAt(0) === '_' ? undefined : v)));
    return new Promise(fertig => {
      eigen.layout(rein, opt).then(ergebnis => {
        if (laufend !== lauf) return;      // abgebrochen: Promise bleibt offen
        clearTimeout(lauf.uhr);
        laufend = null;
        uebertrage(graph, ergebnis);
        fertig(graph);
      }, fehler => {
        if (laufend !== lauf) return;
        steuerung.letzterFehler = String(fehler && (fehler.message || fehler));
        clearTimeout(lauf.uhr);
        laufend = null;
        verwerfen();
        melde('fehler');
      });
    });
  };
  window.ELK = ElkImWorker;
})();
