/* Daidalos-Karte. Liest die eingebettete Messung (daidalos.json), Deutung (deutung.json) und
   Einstellungen und zeichnet sie mit Cytoscape.js und ELK. Rechnet nichts Neues aus, nur
   Darstellung: Layout, Verdichtung eingeklappter Teile, Hervorhebung, Wegsuche über die Kanten.

   Aufbau:
   1. Daten und Index      5. Stil                  9. Bedienung und Start
   2. Zustand              6. Hervorheben, Fokus    10. Sperren und Positionen
   3. Elemente je Ebene    7. Seitenleiste          11. Pfad-Suche
   4. Zeichnen und Layout  8. Sprungadressen        12. Editor-Links
                                                    13. Funktionsebene (seit A09) */
(function () {
  'use strict';

  // ------------------------------------------------------------ 1. Daten und Index
  const M = JSON.parse(document.getElementById('daidalos-daten').textContent);
  const D = JSON.parse(document.getElementById('daidalos-deutung').textContent) ||
    { schema: 1, beschreibungen: {}, bereiche: [], einschaetzungen: [], kanten: {} };
  const E = JSON.parse(document.getElementById('daidalos-einstellungen').textContent) ||
    { editor_link: 'vscode://file/{pfad}:{zeile}', wurzel: null };

  const knoten = new Map(M.knoten.map(k => [k.id, k]));
  const kanteNachId = new Map(M.kanten.map(k => [k.id, k]));
  const befundNachId = new Map(M.befunde.map(b => [b.id, b]));
  const einschaetzung = new Map(D.einschaetzungen.map(e => [e.befund, e]));

  const CODE_SPRACHEN = new Set(['kotlin', 'java', 'c', 'cpp']);
  const GROSS_AB = 150;
  const SAMMEL = 'sammel:ordner';
  // Schriftgröße der Datei-Kästen (und der übrigen Blätter außer Paketen) in px bei Zoom 1.
  const SCHRIFT_DATEI = 11.5;

  const gruppen = M.knoten.filter(k => k.art === 'modul' || k.art === 'ordner');
  const pakete = M.knoten.filter(k => k.art === 'paket');
  const mitKante = new Set();
  M.kanten.forEach(k => { if (k.art === 'nutzt' || k.art === 'jni') { mitKante.add(k.von); mitKante.add(k.nach); } });
  // Auf der Karte: Quellcode-Dateien und jede Datei mit einer Kante (Gradle-Skripte sind gradle-kotlin).
  const istCode = k => CODE_SPRACHEN.has(k.sprache);
  const kartenDateien = M.knoten.filter(k => k.art === 'datei' && (istCode(k) || mitKante.has(k.id)));
  const aufKarte = new Set(kartenDateien.map(d => d.id));
  const gross = kartenDateien.length > GROSS_AB;
  const behaelter = d => d.modul || d.ordner;
  const ebeneVon = k => k.art === 'datei' ? 'datei' : k.art === 'paket' ? 'paket' : 'modul';

  const paketRollen = new Map();
  M.knoten.forEach(d => {
    if (d.art !== 'datei' || !d.paket) return;
    if (!paketRollen.has(d.paket)) paketRollen.set(d.paket, new Set());
    paketRollen.get(d.paket).add(d.rolle);
  });

  // Ordner ohne Kartendateien und ohne Kanten werden auf der Modulebene zu einem Kasten.
  const mitGruppenKante = new Set();
  M.kanten.forEach(k => { if (k.art !== 'enthaelt') { mitGruppenKante.add(k.von); mitGruppenKante.add(k.nach); } });
  const mitKartenDatei = new Set(kartenDateien.map(behaelter));
  const weitereOrdner = gruppen.filter(g => g.art === 'ordner' && !mitKartenDatei.has(g.id) && !mitGruppenKante.has(g.id));
  const inSammel = new Set(weitereOrdner.map(g => g.id));

  // Verdichtete Kanten je (von, nach, rolle) für „einzige Verbindung“ und tragende Datei-Kanten.
  const verdichtet = new Map();
  M.kanten.forEach(k => { if (k.art === 'nutzt' && !k.von.startsWith('datei:')) verdichtet.set(k.von + '|' + k.nach + '|' + k.rolle, k); });
  const dateiKanten = M.kanten.filter(k => k.art === 'nutzt' && k.von.startsWith('datei:'));
  const zyklenVonKante = new Map();
  M.befunde.forEach(b => {
    if (b.regel !== 'zyklus') return;
    b.beleg.kanten.forEach(id => { if (!zyklenVonKante.has(id)) zyklenVonKante.set(id, []); zyklenVonKante.get(id).push(b); });
  });

  // Funktions-Ids stehen nicht in der Strukturansicht; ihre Datei steht in der Id (seit A08).
  const dateiDerFunktion = id => id.startsWith('funktion:') ? 'datei:' + id.slice(9).split('#')[0] : id;
  const kurzFunktion = id => id.includes('#') ? id.split('#').slice(1).join('#') : id;
  // Befunde, die die Schalter „Markierung“ und „detekt“ ein- und ausblenden
  const istMarkierung = b => b.regel === 'markierung-verlassen';
  const istDetekt = b => b.quelle === 'detekt';
  const befundSichtbar = b => (!istMarkierung(b) || zustand.markierung) && (!istDetekt(b) || zustand.detekt);

  function name(id) {
    if (id === SAMMEL) return 'Weitere Ordner';
    if (id.startsWith('funktion:')) return kurzFunktion(id);
    const k = knoten.get(id);
    if (!k) return id;
    if (k.art === 'modul') return k.gradle_pfad;
    if (k.art === 'paket') return k.name;
    if (k.art === 'ordner') return k.pfad === '.' ? '(Wurzel)' : k.pfad + '/';
    return k.pfad.split('/').pop();
  }

  // ------------------------------------------------------------ 2. Zustand
  const zustand = {
    ebene: 'modul',
    mitTests: false,
    // Kantenarten je Ebene; auf der Modulebene wahlweise Gradle oder verdichtete nutzt-Kanten.
    arten: { modul: { gradle: true, nutzt: false, jni: false }, paket: { gradle: false, nutzt: true, jni: false }, datei: { gradle: false, nutzt: true, jni: true } },
    plugins: false,            // gradle-plugin-Kanten zeigen
    zyklen: true,
    markierung: true,          // Befunde der Markierungs-Kette in den Listen zeigen
    detekt: false,             // detekt-Befunde zeigen (detekt hat eine eigene Ausgabe)
    offen: new Set(),          // ausgeklappte Module auf der Dateiebene (nur bei großen Projekten)
    zuletztModul: null,
    // Kantenführung: 'elk' (ELKs orthogonale Führung), 'taxi' oder 'bezier'; siehe Bericht A05.
    kantenfuehrung: 'elk',
    auswahl: null,             // { art: 'knoten' | 'befund' | 'kante' | 'pfad' | 'funktion' | 'fdatei' | 'grenze', … }
    // Funktionsebene (A09): gezeigte Datei, Wegmodus, Schalter, aufgeklappte Nachbardateien
    fDatei: null,
    zuletztDatei: null,
    weg: null,                 // { art: 'weg', start, richtung: 'vor' | 'rueck', tiefe } | { art: 'pfad', von, nach }
    wegErgebnis: null,
    fTiefe: 3,
    fLesen: false,             // Lesezugriffe (lesen/schreiben) zeigen und folgen (gemerkter Stand)
    wegLesen: false,           // Wegmodus: Lesezugriffe; ab markierter Start-Funktion an (A09b)
    fUnsicher: true,           // Dateiansicht: unsichere Kanten zeigen (Standard an)
    wegUnsicher: false,        // Wegmodus: unsicheren Kanten folgen (Standard aus, wie daidalos aufrufe)
    fAuf: new Set(),           // einzeln aufgeklappte Nachbardateien
    fZu: new Set(),
    fKaesten: 0
  };
  zustand.arten.funktion = {};
  const ARTEN_JE_EBENE = { modul: ['gradle', 'nutzt'], paket: ['nutzt'], datei: ['nutzt', 'jni'], funktion: [] };

  function sichtbareDatei(d) { return !d.fremd && (zustand.mitTests || d.rolle !== 'test'); }
  function sichtbaresPaket(p) {
    if (p.fremd) return false;
    const rollen = paketRollen.get(p.id) || new Set(['produktiv']);
    return zustand.mitTests || rollen.has('produktiv');
  }
  function rolleOk(k) { return zustand.mitTests || k.rolle === 'produktiv'; }

  // Standard beim ersten Öffnen der Dateiebene: zuletzt gewähltes Modul, sonst das größte.
  function standardOffen() {
    if (!gross || zustand.offen.size) return;
    if (zustand.zuletztModul) { zustand.offen.add(zustand.zuletztModul); return; }
    const zahl = new Map();
    kartenDateien.forEach(d => { if (sichtbareDatei(d)) zahl.set(behaelter(d), (zahl.get(behaelter(d)) || 0) + 1); });
    let best = null;
    gruppen.forEach(g => { if ((zahl.get(g.id) || 0) > (best ? zahl.get(best) : 0)) best = g.id; });
    if (best) zustand.offen.add(best);
  }
  const istOffen = g => !gross || zustand.offen.has(g);

  // ------------------------------------------------------------ 3. Elemente je Ebene
  const messer = document.createElement('canvas').getContext('2d');
  function breiteVon(zeilen, schrift) {
    messer.font = schrift;
    return Math.max(...zeilen.map(z => messer.measureText(z).width));
  }
  // Blätter tragen oben rechts Symbole (Schloss; bei Dateien Code, Editor, Schloss).
  function blatt(id, zeilen, typ, extra, mono) {
    const schrift = (mono ? '11px ' + tok('--mono') : SCHRIFT_DATEI + 'px ' + tok('--font'));
    const text = Math.ceil(breiteVon(zeilen, schrift)) + 28;
    const datei = typ === 'datei';
    const w = datei ? Math.max(82, text) : Math.max(80, text + 18);
    const h = datei ? 30 + 15 * zeilen.length : 16 + 16 * zeilen.length;
    return { group: 'nodes', data: Object.assign({ id, label: zeilen.join('\n'), typ, w, h }, extra) };
  }
  const breite = g => 1 + Math.min(4, Math.log2(1 + (g || 1)) * 0.7);

  // Kanten zusammenführen: gleiche Enden und Art werden eine Kante mit Summe der Gewichte.
  function sammler() {
    const liste = new Map();
    return {
      add(quelle, ziel, art, k, verdichtet) {
        if (quelle === ziel) return;
        const id = verdichtet ? 'v:' + art + ':' + quelle + '->' + ziel : k.id;
        let e = liste.get(id);
        if (!e) {
          e = { group: 'edges', data: { id, source: quelle, target: ziel, art, gewicht: 0, kanten: [], unsicher: true, verdichtet: !!verdichtet } };
          liste.set(id, e);
        }
        e.data.gewicht += k.gewicht || 1;
        e.data.kanten.push(k.id);
        e.data.unsicher = e.data.unsicher && k.sicher === false;
      },
      werte() { return [...liste.values()].sort((a, b) => a.data.id < b.data.id ? -1 : a.data.id > b.data.id ? 1 : 0); }
    };
  }

  function zyklusKanten() {
    // Kanten-Ids der Zyklen, die zur aktuellen Ansicht passen.
    const ids = new Set();
    M.befunde.forEach(b => {
      if (b.regel !== 'zyklus' || b.beleg.ebene !== zustand.ebene) return;
      if (b.beleg.rolle !== 'produktiv' && !zustand.mitTests) return;
      b.beleg.kanten.forEach(id => ids.add(id));
    });
    return ids;
  }

  // Module, die als Ziel von gradle-plugin-Kanten dienen: Modul → Zahl der Quellen.
  function pluginZiele() {
    const ziele = new Map();
    M.kanten.forEach(k => {
      if (k.art !== 'gradle-plugin' || !rolleOk(k)) return;
      if (!ziele.has(k.nach)) ziele.set(k.nach, new Set());
      ziele.get(k.nach).add(k.von);
    });
    return ziele;
  }

  function elemente() {
    if (zustand.ebene === 'funktion') return funktionsElemente();
    const els = [];
    const kanten = sammler();
    const art = zustand.arten[zustand.ebene];
    if (zustand.ebene === 'modul') {
      const plugin = art.gradle && !zustand.plugins ? pluginZiele() : new Map();
      gruppen.forEach(g => {
        if (inSammel.has(g.id)) return;
        const zeilen = [name(g.id), (g.dateien || 0) + ' Dateien · ' + (g.zeilen || 0) + ' Zeilen'];
        if (plugin.has(g.id)) zeilen.push('Plugin für ' + plugin.get(g.id).size + ' Module');
        els.push(blatt(g.id, zeilen, 'gruppe', { ref: g.id, art: g.art }));
      });
      if (weitereOrdner.length) {
        const dateien = weitereOrdner.reduce((s, g) => s + (g.dateien || 0), 0);
        els.push(blatt(SAMMEL, ['Weitere Ordner', weitereOrdner.length + ' Ordner · ' + dateien + ' Dateien'], 'sammel', { ref: SAMMEL }));
      }
      M.kanten.forEach(k => {
        if (art.gradle && k.art.startsWith('gradle-') && rolleOk(k) && (zustand.plugins || k.art !== 'gradle-plugin')) kanten.add(k.von, k.nach, k.art, k);
        if (art.nutzt && k.art === 'nutzt' && rolleOk(k) && istGruppe(k.von) && istGruppe(k.nach)) kanten.add(k.von, k.nach, 'nutzt', k);
      });
    } else if (zustand.ebene === 'paket') {
      const fremdBox = new Map();
      gruppen.forEach(g => els.push({ group: 'nodes', data: { id: g.id, label: name(g.id), typ: 'gruppe', ref: g.id, art: g.art } }));
      pakete.forEach(p => {
        const g = p.modul || p.ordner;
        if (p.fremd) { fremdBox.set(p.id, 'fremd:' + g); return; }
        if (sichtbaresPaket(p)) els.push(blatt(p.id, [p.name], 'paket', { parent: g, ref: p.id }, true));
      });
      zaehleFremd(fremdBox, 'Pakete').forEach(e => els.push(e));
      ohneLeereBehaelter(els);
      const abb = id => fremdBox.get(id) || id;
      const da = new Set(els.map(e => e.data.id));
      if (art.nutzt) M.kanten.forEach(k => {
        if (k.art !== 'nutzt' || !rolleOk(k) || !k.von.startsWith('paket:')) return;
        const q = abb(k.von), z = abb(k.nach);
        if (da.has(q) && da.has(z)) kanten.add(q, z, 'nutzt', k, q !== k.von || z !== k.nach);
      });
    } else {
      standardOffen();
      const ort = new Map();       // Datei-Id → sichtbarer Knoten (Datei, Fremd-Kasten oder Modul)
      const fremd = new Map();
      const sichtbarePakete = new Set();
      const anzahl = new Map();
      kartenDateien.forEach(d => { if (sichtbareDatei(d)) anzahl.set(behaelter(d), (anzahl.get(behaelter(d)) || 0) + 1); });
      gruppen.forEach(g => {
        if (istOffen(g.id)) els.push({ group: 'nodes', data: { id: g.id, label: name(g.id), typ: 'gruppe', ref: g.id, art: g.art } });
        else els.push(blatt(g.id, [name(g.id), (anzahl.get(g.id) || 0) + ' Dateien · eingeklappt'], 'zu', { ref: g.id, art: g.art }));
      });
      kartenDateien.forEach(d => {
        const g = behaelter(d);
        if (!istOffen(g)) { if (sichtbareDatei(d) || d.fremd) ort.set(d.id, g); return; }
        if (d.fremd) { fremd.set(d.id, 'fremd:' + g); ort.set(d.id, 'fremd:' + g); return; }
        if (!sichtbareDatei(d)) return;
        const eltern = d.paket || g;
        if (d.paket) sichtbarePakete.add(d.paket);
        els.push(blatt(d.id, [name(d.id)], 'datei', { parent: eltern, ref: d.id, rolle: d.rolle }));
        ort.set(d.id, d.id);
      });
      pakete.forEach(p => { if (sichtbarePakete.has(p.id)) els.push({ group: 'nodes', data: { id: p.id, label: p.name, typ: 'paket', parent: p.modul || p.ordner, ref: p.id } }); });
      zaehleFremd(fremd, 'Dateien').forEach(e => els.push(e));
      ohneLeereBehaelter(els);
      M.kanten.forEach(k => {
        if (!((k.art === 'nutzt' && art.nutzt) || (k.art === 'jni' && art.jni)) || !rolleOk(k) || !k.von.startsWith('datei:')) return;
        const q = ort.get(k.von), z = ort.get(k.nach);
        if (q && z) kanten.add(q, z, k.art, k, q !== k.von || z !== k.nach);
      });
    }
    const zyk = zyklusKanten();
    const mitLabel = zustand.ebene !== 'datei';
    kanten.werte().forEach(e => {
      const d = e.data;
      d.breite = breite(d.gewicht);
      d.label = mitLabel ? kurzArt(d.art) + ' · ' + d.gewicht : '';
      const cls = [];
      if (d.unsicher) cls.push('unsicher');
      if (d.verdichtet) cls.push('verdichtet');
      if (d.kanten.some(id => zyk.has(id))) cls.push('zyk');
      if (d.art === 'jni') cls.push('jni');
      if (d.art === 'gradle-plugin') cls.push('plugin');
      // Dateiebene: Kanten innerhalb eines Pakets blasser.
      const a = knoten.get(d.source), b = knoten.get(d.target);
      if (zustand.ebene === 'datei' && a && b && a.art === 'datei' && b.art === 'datei' && a.paket && a.paket === b.paket) cls.push('innen');
      e.classes = cls.join(' ');
      els.push(e);
    });
    els.forEach(e => {
      if (e.group !== 'nodes') return;
      const k = knoten.get(e.data.id);
      const cls = [];
      if (e.data.rolle === 'test') cls.push('test');
      if (e.data.typ === 'fremd') cls.push('fremd');
      if ((k && k.art === 'ordner') || e.data.typ === 'sammel') cls.push('ordner');
      e.classes = cls.join(' ');
    });
    return els;
  }
  // Module und Ordner ohne sichtbaren Inhalt fallen auf Paket- und Dateiebene weg.
  function ohneLeereBehaelter(els) {
    const eltern = new Set(els.map(e => e.data.parent).filter(Boolean));
    for (let i = els.length - 1; i >= 0; i--) {
      const d = els[i].data;
      if (d.typ === 'gruppe' && !eltern.has(d.id)) els.splice(i, 1);
    }
  }
  function istGruppe(id) { const k = knoten.get(id); return !!k && (k.art === 'modul' || k.art === 'ordner'); }
  function kurzArt(art) { return art.startsWith('gradle-') ? art.slice(7) : art; }
  function zaehleFremd(abbildung, was) {
    const zahl = new Map();
    abbildung.forEach(box => zahl.set(box, (zahl.get(box) || 0) + 1));
    return [...zahl.keys()].sort().map(box => blatt(box, ['Fremd · ' + zahl.get(box) + ' ' + was], 'fremd', { parent: box.slice(6), ref: box.slice(6) }));
  }

  // ------------------------------------------------------------ 4. Zeichnen und Layout
  const ruhig = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  const cy = cytoscape({
    container: document.getElementById('cy'), elements: [], style: [],
    wheelSensitivity: 0.3, minZoom: 0.03, maxZoom: 3, boxSelectionEnabled: false, autoungrabify: false
  });
  const layoutCache = new Map();
  const zeiten = {};
  let lauf = 0;
  // Stil-Eigenschaften, mit denen cytoscape-elk ELKs Kantenführung auf eine Kante legt.
  const ROUTEN_STIL = ['curve-style', 'edge-distances', 'source-endpoint', 'target-endpoint', 'segment-weights', 'segment-distances'];

  function layoutSchluessel() {
    if (zustand.ebene === 'funktion') {
      const w = zustand.weg;
      const weg = !w ? '' : w.art === 'weg' ? [w.start, w.richtung, w.tiefe].join('~') : ['pfad', w.von, w.nach].join('~');
      return ['funktion', zustand.fDatei, weg, lesenAn() ? 'l' : '', unsicherAn() ? 'u' : '', zustand.mitTests ? 't' : 'p',
        zustand.markierung ? 'm' : '', [...zustand.fAuf].sort().join(','), zustand.kantenfuehrung].join('|');
    }
    const a = zustand.arten[zustand.ebene];
    return [zustand.ebene, zustand.mitTests ? 't' : 'p', a.gradle ? 'g' : '', a.nutzt ? 'n' : '', a.jni ? 'j' : '',
      zustand.ebene === 'modul' && zustand.plugins ? 'pl' : '', zustand.kantenfuehrung,
      zustand.ebene === 'datei' && gross ? [...zustand.offen].sort().join(',') : ''].join('|');
  }
  // Kantenabstände gegen lange Kabelstränge (A05b, an Sketchorus verglichen). ELK liest Abstände je
  // Behälter, daher gelten sie für die Wurzel und über nodeLayoutOptions für jeden Behälter.
  const KANTEN_ABSTAND = {
    'elk.layered.spacing.edgeEdgeBetweenLayers': 18,
    'elk.layered.spacing.edgeNodeBetweenLayers': 28,
    'elk.spacing.edgeEdge': 14
  };
  const BEHAELTER_OPTIONEN = Object.assign({ 'elk.padding': '[top=30,left=14,bottom=14,right=14]' }, KANTEN_ABSTAND);
  // Wegmodus (A09b): Optionen gegen den Kabelstrang am Start, an Sketchorus verglichen (Bericht).
  // Kanten gleicher Quelle laufen als ein Strang und fächern sich erst vor der Zielspalte auf
  // (mergeEdges); verteilte Ports (portConstraints) ließen 18 Kanten nebeneinander laufen.
  const WEG_ELK = { 'elk.layered.mergeEdges': true };
  const ELK = Object.assign({
    algorithm: 'layered',
    'elk.direction': 'DOWN',
    'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
    'elk.layered.spacing.nodeNodeBetweenLayers': 46,
    'elk.spacing.nodeNode': 22,
    'elk.layered.considerModelOrder.strategy': 'NODES_AND_EDGES',
    'elk.layered.crossingMinimization.forceNodeModelOrder': false,
    'elk.randomSeed': 1
  }, KANTEN_ABSTAND);

  // Zeichnet die aktuelle Ebene neu. Liefert ein Promise, das nach dem Layout erfüllt ist (true)
  // oder mit false, wenn ein neueres Zeichnen es abgelöst hat. ELK rechnet im Web Worker
  // (elk_lauf.js); ein laufendes Layout wird abgebrochen, sobald ein neues beginnt. Braucht ELK
  // länger als die Zeitgrenze, greift ein Ersatzlayout mit dem Hinweis „vereinfachte Anordnung“.
  let gezeichnet = null;
  let offenesLayout = null;    // fertig() des laufenden Layouts
  const elkLauf = window.daidalosElk;
  // Passt die gezeichnete Karte nicht mehr zum Zustand (Ebene, Schalter, ausgeklappte Module)?
  const veraltet = () => layoutSchluessel() !== gezeichnet || cy.nodes().empty();
  function zeichne() {
    const nr = ++lauf;
    const schluessel = layoutSchluessel();
    gezeichnet = schluessel;
    const beginn = performance.now();
    elkLauf.abbrechen();
    if (offenesLayout) { const f = offenesLayout; offenesLayout = null; f(false); }
    fluss.stopp();
    document.documentElement.dataset.zustand = 'rechnet';
    cy.batch(() => { cy.elements().remove(); cy.add(elemente()); });
    cy.style(stil());
    zeigeSchalter();
    return new Promise(fertig => {
      offenesLayout = fertig;
      const ende = ersatz => {
        if (nr !== lauf) return fertig(false);
        offenesLayout = null;
        zeigeAnordnung(ersatz);
        wendePositionenAn();
        sperren();
        fKlassen();
        if (zustand.ebene === 'datei' && !zustand.auswahl) startAnsicht();
        else if (zustand.ebene === 'funktion') fStartAnsicht();
        else einpassen(cy.elements(), 30);
        if (!gespeichert && !ersatz) zeiten[schluessel] = Math.round(performance.now() - beginn);
        // Startzeit: vom Beginn der Navigation bis zur ersten fertigen Ansicht (A09).
        if (zeiten.bereit === undefined) zeiten.bereit = Math.round(performance.now());
        document.getElementById('lade').hidden = true;
        document.documentElement.dataset.zustand = 'bereit';
        fertig(true);
      };
      const gespeichert = layoutCache.get(schluessel);
      if (gespeichert) {
        cy.layout({ name: 'preset', positions: n => gespeichert.pos[n.id()], fit: false }).run();
        cy.batch(() => Object.entries(gespeichert.routen).forEach(([id, s]) => cy.getElementById(id).style(s)));
        ende();
        return;
      }
      document.getElementById('lade').hidden = false;
      const elk = zustand.kantenfuehrung === 'elk';
      // Funktionsebene: Aufrufer links, Gerufene rechts; Kanten innerhalb einer Spalte des
      // Wirkungswegs (ueberschreibt/actual) zählen nicht für das Layout.
      const funktion = zustand.ebene === 'funktion';
      const layout = cy.elements().not('.ohneLayout').layout({
        name: 'elk', fit: false, animate: false, nodeDimensionsIncludeLabels: false,
        useElkEdgeGeometry: elk,
        elk: Object.assign({}, ELK, elk ? { 'elk.edgeRouting': 'ORTHOGONAL' } : {}, funktion ? { 'elk.direction': 'RIGHT' } : {}, funktion && zustand.weg ? WEG_ELK : {}),
        nodeLayoutOptions: n => n.isParent() ? Object.assign({}, BEHAELTER_OPTIONEN) : undefined
      });
      elkLauf.beiAbbruch = grund => {
        if (nr !== lauf) return;
        ersatzLayout();
        ende(grund);
      };
      layout.one('layoutstop', () => {
        if (nr === lauf) {
          const pos = {}, routen = {};
          cy.nodes().forEach(n => { if (!n.isParent()) pos[n.id()] = Object.assign({}, n.position()); });
          cy.edges().forEach(e => {
            const s = e.scratch('_elkEdgeStyle');
            if (s) routen[e.id()] = Object.assign({}, s.applied);
          });
          layoutCache.set(schluessel, { pos, routen });
        }
        ende();
      });
      // Das Layout erst nach dem nächsten Bild starten, damit „Layout wird berechnet“ sichtbar wird.
      requestAnimationFrame(() => setTimeout(() => { if (nr === lauf) layout.run(); else fertig(false); }, 0));
    });
  }

  // Ersatz, wenn ELK nicht rechtzeitig fertig wird: Cytoscape „breadthfirst“, mit Rahmen (Behältern)
  // „grid“, die Kinder eines Rahmens nebeneinander. Wird nicht zwischengespeichert.
  function ersatzLayout() {
    const els = cy.elements().not('.ohneLayout');
    const mitRahmen = cy.nodes(':parent').nonempty();
    const pfadVon = n => n.ancestors().map(a => a.id()).reverse().concat(n.id()).join('/');
    els.layout(mitRahmen
      ? { name: 'grid', fit: false, animate: false, avoidOverlap: true, avoidOverlapPadding: 24, sort: (a, b) => pfadVon(a) < pfadVon(b) ? -1 : pfadVon(a) > pfadVon(b) ? 1 : 0 }
      : { name: 'breadthfirst', directed: true, fit: false, animate: false, spacingFactor: 1.2 }).run();
  }
  const anordnung = document.getElementById('anordnung');
  function zeigeAnordnung(grund) {
    const ersatz = !!grund;
    anordnung.textContent = !ersatz ? '' : 'vereinfachte Anordnung: ' + (grund === 'zeitgrenze' ? 'ELK hat das Layout nicht in ' + elkLauf.zeitgrenze / 1000 + ' s geschafft' : grund === 'kein-worker' ? 'ELK ließ sich nicht starten' : 'ELK meldete einen Fehler');
    anordnung.hidden = !ersatz;
    document.documentElement.dataset.anordnung = ersatz ? 'ersatz' : 'elk';
  }

  // Dateiebene beim Öffnen: Wird beim Einpassen alles unlesbar klein (Dateinamen unter etwa 9 px),
  // zeigt sie das größte Paket in lesbarer Größe. „Einpassen“ zeigt weiter alles.
  const LESBAR = 9 / SCHRIFT_DATEI;
  function startAnsicht() {
    if (ziel(cy.elements(), 30).zoom >= LESBAR) { einpassen(cy.elements(), 30); return; }
    let best = null, zahl = -1;
    cy.nodes('[typ="paket"]').forEach(p => {
      if (!p.isParent()) return;
      const n = p.descendants().filter(x => x.isChildless()).length;
      if (n > zahl || (n === zahl && p.id() < best.id())) { best = p; zahl = n; }
    });
    if (!best) { einpassen(cy.elements(), 30); return; }
    const bb = best.boundingBox();
    const v = ziel(best, 30);
    const zoom = Math.max(v.zoom, Math.min(1, LESBAR * 1.05));
    const w = cy.width(), h = cy.height();
    const x = bb.w * zoom <= w - 60 ? w / 2 - zoom * (bb.x1 + bb.w / 2) : 30 - zoom * bb.x1;
    const y = bb.h * zoom <= h - 60 ? h / 2 - zoom * (bb.y1 + bb.h / 2) : 40 - zoom * bb.y1;
    cy.viewport({ zoom, pan: { x, y } });
  }

  // ------------------------------------------------------------ 5. Stil
  const tok = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const SCHLOSS_ZU = c => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><rect x='3' y='7' width='10' height='8' rx='1.5' fill='${c}'/><path d='M5.2 7V5.2a2.8 2.8 0 0 1 5.6 0V7' fill='none' stroke='${c}' stroke-width='1.6'/></svg>`;
  const SCHLOSS_AUF = c => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><rect x='3' y='7' width='10' height='8' rx='1.5' fill='${c}'/><path d='M5.2 7V4.6a2.8 2.8 0 0 1 5.5-.8' fill='none' stroke='${c}' stroke-width='1.6'/></svg>`;
  const SYMBOL_CODE = c => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M5.5 4L1.5 8l4 4M10.5 4l4 4-4 4' fill='none' stroke='${c}' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/></svg>`;
  const SYMBOL_EDITOR = c => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M9 2.5h4.5V7M13.5 2.5L7.5 8.5M12 9.5v3.5a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h3.5' fill='none' stroke='${c}' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'/></svg>`;
  // Funktionsebene: Schild (markiert), Ausnahme, Punkt (detekt-Fund)
  const SCHILD = c => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M8 1.2l5.6 2.1v4.3c0 3.5-2.4 5.9-5.6 7.1-3.2-1.2-5.6-3.6-5.6-7.1V3.3z' fill='${c}'/></svg>`;
  const AUSNAHME = c => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><circle cx='8' cy='8' r='5.6' fill='none' stroke='${c}' stroke-width='1.9'/><path d='M4.1 11.9l7.8-7.8' stroke='${c}' stroke-width='1.9'/></svg>`;
  const PUNKT = c => `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><circle cx='8' cy='8' r='5' fill='${c}'/></svg>`;
  const SVG_ZU = SCHLOSS_ZU('currentColor'), SVG_AUF = SCHLOSS_AUF('currentColor');
  const SVG_CODE = SYMBOL_CODE('currentColor'), SVG_EDITOR = SYMBOL_EDITOR('currentColor');
  const bild = svg => 'data:image/svg+xml;utf8,' + encodeURIComponent(svg);

  function stil() {
    const f = tok('--font'), mono = tok('--mono');
    const o = n => parseFloat(tok(n));
    const symbol = { 'background-fit': 'none', 'background-clip': 'none', 'background-width': 13, 'background-height': 13, 'background-position-x': '100%', 'background-position-y': '0%', 'background-offset-x': -5, 'background-offset-y': 5 };
    const dreifach = v => [v, v, v];
    const editorFarbe = editorBasis() ? tok('--accent') : tok('--muted');
    const editorDeck = editorBasis() ? 0.85 : 0.35;
    const regeln = [
      { selector: 'node', style: Object.assign({ 'font-family': f, color: tok('--fg'), 'text-wrap': 'wrap', 'font-size': SCHRIFT_DATEI, 'text-valign': 'center', 'text-halign': 'center', shape: 'round-rectangle', 'background-color': tok('--node'), 'border-width': 1, 'border-color': tok('--edge'), label: 'data(label)', 'line-height': 1.35, 'min-zoomed-font-size': 5,
        'background-image': bild(SCHLOSS_ZU(tok('--muted'))), 'background-image-opacity': 0.7 }, symbol) },
      { selector: 'node.offen', style: { 'background-image': bild(SCHLOSS_AUF(tok('--accent'))), 'background-image-opacity': 1 } },
      { selector: 'node[w]', style: { width: 'data(w)', height: 'data(h)' } },
      { selector: 'node[typ="gruppe"]', style: { 'background-color': tok('--mod'), 'border-width': 1.5, 'font-size': 13, 'font-weight': 600, 'min-zoomed-font-size': 3 } },
      { selector: 'node[typ="gruppe"]:parent', style: { 'text-valign': 'top', 'text-margin-y': -5, padding: 14 } },
      { selector: 'node[typ="gruppe"]:childless', style: { 'background-color': tok('--node') } },
      { selector: 'node[typ="zu"], node[typ="sammel"]', style: { 'background-color': tok('--mod'), 'border-width': 1.5, 'border-style': 'dashed', 'font-weight': 600 } },
      { selector: 'node[typ="paket"]', style: { 'font-family': mono, 'font-size': 11, 'min-zoomed-font-size': 4 } },
      { selector: 'node[typ="paket"]:parent', style: { 'background-color': tok('--pkg'), 'border-color': tok('--line'), 'text-valign': 'top', 'text-margin-y': -4, color: tok('--muted'), 'font-size': 10.5, padding: 12 } },
      { selector: 'node[typ="datei"]', style: { 'text-margin-y': 6, 'min-zoomed-font-size': 8,
        'background-image': [bild(SYMBOL_CODE(tok('--muted'))), bild(SYMBOL_EDITOR(editorFarbe)), bild(SCHLOSS_ZU(tok('--muted')))],
        'background-fit': dreifach('none'), 'background-clip': dreifach('none'), 'background-width': dreifach(13), 'background-height': dreifach(13),
        'background-position-x': dreifach('100%'), 'background-position-y': dreifach('0%'), 'background-offset-x': [-41, -23, -5], 'background-offset-y': dreifach(5), 'background-image-opacity': [0.35, editorDeck, 0.7] } },
      { selector: 'node[typ="datei"].offen', style: { 'background-image': [bild(SYMBOL_CODE(tok('--muted'))), bild(SYMBOL_EDITOR(editorFarbe)), bild(SCHLOSS_AUF(tok('--accent')))], 'background-image-opacity': [0.35, editorDeck, 1] } },
      { selector: 'node.ordner', style: { 'border-style': 'dotted' } },
      { selector: 'node.test', style: { 'border-style': 'dashed', 'font-style': 'italic', color: tok('--muted') } },
      { selector: 'node.fremd', style: { 'background-color': tok('--pkg'), 'border-style': 'dotted', color: tok('--muted'), 'font-style': 'italic' } },
      { selector: 'edge', style: { 'curve-style': zustand.kantenfuehrung === 'taxi' ? 'taxi' : 'bezier', 'taxi-direction': 'downward', 'taxi-turn': '50%', 'taxi-turn-min-distance': 8,
        width: 'data(breite)', 'line-color': tok('--edge'), 'target-arrow-color': tok('--edge'), 'target-arrow-shape': 'triangle', 'arrow-scale': 0.9, label: 'data(label)', 'font-size': 10, 'min-zoomed-font-size': 6, color: tok('--muted'), 'font-family': f, 'text-background-color': tok('--panel'), 'text-background-opacity': 0.9, 'text-background-padding': 2, 'text-rotation': 'autorotate', opacity: 0.85 } },
      { selector: 'edge.innen', style: { opacity: 0.32 } },
      { selector: 'edge.jni', style: { 'line-color': tok('--adr'), 'target-arrow-color': tok('--adr') } },
      { selector: 'edge.plugin', style: { 'line-style': 'dotted' } },
      { selector: 'edge.unsicher', style: { 'line-style': 'dashed', 'line-dash-pattern': [6, 4] } },
      { selector: 'edge.verdichtet', style: { 'line-style': 'dashed', 'line-dash-pattern': [2, 4] } }
    ];
    if (zustand.zyklen) regeln.push({ selector: 'edge.zyk', style: { 'line-color': tok('--crit'), 'target-arrow-color': tok('--crit'), opacity: 1 } });
    regeln.push(...funktionsStil(f, mono));
    regeln.push(
      // Abgestufter Fokus: Knoten und Kanten; Behälter ohne Fokus-Inhalt nur Rand und Schrift.
      { selector: '.n1', style: { opacity: o('--o-n1') } },
      { selector: '.n2', style: { opacity: o('--o-n2') } },
      { selector: '.blass', style: { opacity: o('--o-blass') } },
      { selector: 'node.blassB', style: { 'border-opacity': o('--o-n2'), 'text-opacity': o('--o-n2'), 'background-opacity': o('--o-n2'), 'background-image-opacity': o('--o-blass') } },
      { selector: 'node.hl', style: { 'overlay-color': tok('--accent'), 'overlay-opacity': 0.14, 'overlay-padding': 5 } },
      { selector: 'edge.hl', style: { 'line-color': tok('--accent'), 'target-arrow-color': tok('--accent'), width: 3, opacity: 1 } },
      { selector: 'edge.raus', style: { 'line-color': tok('--accent'), 'target-arrow-color': tok('--accent') } },
      { selector: 'edge.rein', style: { 'line-color': tok('--fg'), 'target-arrow-color': tok('--fg') } },
      { selector: 'edge.fluss', style: { 'line-style': 'dashed', 'line-dash-pattern': [8, 6] } },
      { selector: 'edge.fluss2', style: { 'line-style': 'dashed', 'line-dash-pattern': [4, 6], width: 1.6 } },
      { selector: 'node.gewaehlt', style: { 'border-color': tok('--accent'), 'border-width': 3 } },
      { selector: 'edge.kgewaehlt', style: { 'line-color': tok('--accent'), 'target-arrow-color': tok('--accent'), width: 5, opacity: 1 } },
      { selector: 'node.einstieg', style: { 'border-color': tok('--warn'), 'border-width': 3.5 } },
      { selector: 'edge.einstieg', style: { 'line-color': tok('--warn'), 'target-arrow-color': tok('--warn'), width: 2.4, opacity: 1, label: 'Einstieg', color: tok('--warn') } }
    );
    if (zustand.zyklen) regeln.push({ selector: 'edge.zyk.hl', style: { 'line-color': tok('--crit'), 'target-arrow-color': tok('--crit'), width: 3 } });
    // Grenzkanten behalten ihre Farbe auch im Fokus.
    regeln.push({ selector: 'edge.grenze.hl, edge.grenze.rein, edge.grenze.raus, edge.grenze.kgewaehlt', style: { 'line-color': tok('--warn'), 'target-arrow-color': tok('--warn') } });
    regeln.push({ selector: 'edge.trenn', style: { 'line-color': tok('--crit'), 'target-arrow-color': tok('--crit'), width: 6, opacity: 1, label: 'data(trennText)', color: tok('--crit'), 'font-weight': 700, 'font-size': 12 } });
    return regeln;
  }

  // Funktionsebene: Rahmen für Dateien und Klassen, Kästen für Funktionen mit Symbolen je
  // Kombination aus markiert (1), Ausnahme (2) und detekt-Fund (4); Linienarten je Kante.
  function funktionsStil(f, mono) {
    const regeln = [
      { selector: 'node[typ="fdatei"]', style: { 'background-color': tok('--mod'), 'border-width': 1.5, 'font-size': 13, 'font-weight': 600, 'text-valign': 'top', 'text-margin-y': -5, padding: 16, 'min-zoomed-font-size': 3 } },
      { selector: 'node[typ="fnachbar"]', style: { 'background-color': tok('--pkg'), 'border-style': 'dashed', 'border-color': tok('--line'), 'font-size': 11.5, color: tok('--muted'), 'text-valign': 'top', 'text-margin-y': -4, padding: 12, 'min-zoomed-font-size': 4 } },
      { selector: 'node[typ="fklasse"]', style: { 'background-color': tok('--pkg'), 'border-color': tok('--line'), 'font-family': mono, 'font-size': 11, color: tok('--muted'), 'text-valign': 'top', 'text-margin-y': -4, padding: 12, 'min-zoomed-font-size': 4 } },
      { selector: 'node[typ="fzu"]', style: { 'background-color': tok('--mod'), 'border-width': 1.5, 'border-style': 'dashed', 'font-weight': 600 } },
      { selector: 'node[typ="funktion"]', style: { 'font-family': f, 'min-zoomed-font-size': 6 } },
      { selector: 'node[typ="funktion"].ohneKoerper', style: { 'background-opacity': 0.35, 'border-style': 'dashed', color: tok('--muted') } }
    ];
    const bild1 = { 'background-fit': 'none', 'background-clip': 'none', 'background-width': 11, 'background-height': 11 };
    for (let sym = 0; sym < 8; sym++) {
      [false, true].forEach(offen => {
        const b = [[offen ? SCHLOSS_AUF(tok('--accent')) : SCHLOSS_ZU(tok('--muted')), '100%', -5, '0%', 5, offen ? 1 : 0.7]];
        if (sym & 1) b.push([SCHILD(tok('--warn')), '0%', 5, '0%', 5, 1]);
        if (sym & 2) b.push([AUSNAHME(tok('--adr')), '0%', sym & 1 ? 19 : 5, '0%', 5, 1]);
        if (sym & 4) b.push([PUNKT(tok('--crit')), '100%', -5, '100%', -4, 1]);
        const spalte = i => b.map(x => x[i]);
        const st = { 'background-image': spalte(0).map(bild), 'background-position-x': spalte(1), 'background-offset-x': spalte(2), 'background-position-y': spalte(3), 'background-offset-y': spalte(4), 'background-image-opacity': spalte(5) };
        Object.keys(bild1).forEach(s => { st[s] = b.map(() => bild1[s]); });
        regeln.push({ selector: `node[typ="funktion"][sym=${sym}]${offen ? '.offen' : ''}`, style: st });
      });
    }
    regeln.push(
      { selector: 'edge.zugriff', style: { 'line-color': tok('--muted'), 'target-arrow-color': tok('--muted'), 'arrow-scale': 0.6, opacity: 0.7 } },
      { selector: 'edge.punkt', style: { 'line-style': 'dotted', 'line-dash-pattern': [1, 3], 'target-arrow-shape': 'triangle-backcurve' } },
      { selector: 'node.grenzziel', style: { 'border-color': tok('--warn'), 'border-width': 3 } },
      { selector: 'edge.grenze', style: { 'line-color': tok('--warn'), 'target-arrow-color': tok('--warn'), width: 2.6, opacity: 1 } }
    );
    return regeln;
  }

  // ------------------------------------------------------------ 6. Hervorheben, Fokus, Fluss
  const pfadinfo = document.getElementById('pfadinfo');
  const blattVon = n => n.isParent() ? n.descendants().filter(x => x.isChildless()) : n;

  // Fluss: hervorgehobene Kanten bewegen sich in Pfeilrichtung, über ein einziges Taktsignal.
  const fluss = (() => {
    let k1 = null, k2 = null, lauf = 0, versatz = 0, zuletzt = 0;
    function schritt(t) {
      if (t - zuletzt > 33) {
        versatz = (versatz - 1.2) % 1400;
        cy.batch(() => { k1.style('line-dash-offset', versatz); k2.style('line-dash-offset', versatz * 0.55); });
        zuletzt = t;
      }
      lauf = requestAnimationFrame(schritt);
    }
    return {
      start(a, b) {
        this.stopp();
        k1 = a || cy.collection(); k2 = (b || cy.collection()).not(k1);
        k1.addClass('fluss'); k2.addClass('fluss2');
        if (!ruhig() && (k1.nonempty() || k2.nonempty())) lauf = requestAnimationFrame(schritt);
      },
      stopp() {
        if (lauf) cancelAnimationFrame(lauf);
        lauf = 0;
        if (k1 && k1.cy() === cy) k1.removeClass('fluss').removeStyle('line-dash-offset');
        if (k2 && k2.cy() === cy) k2.removeClass('fluss2').removeStyle('line-dash-offset');
        k1 = k2 = null;
      },
      stand() {
        return { laeuft: !!lauf, kanten: k1 ? k1.map(e => e.id()).sort() : [], kanten2: k2 ? k2.map(e => e.id()).sort() : [], versatz };
      }
    };
  })();

  function leeren() {
    fluss.stopp();
    cy.elements().removeClass('blass blassB n1 n2 hl gewaehlt kgewaehlt einstieg trenn rein raus');
    cy.edges().removeData('trennText');
    pfadinfo.hidden = true;
  }
  const kantenMit = ids => { const s = new Set(ids); return cy.edges().filter(e => e.data('kanten').some(id => s.has(id))); };

  // Alles außer `bleibt` wird blass; Behälter, die nichts davon enthalten, nur an Rand und Schrift.
  function abblenden(bleibt) {
    const blaetter = bleibt.nodes().filter(n => n.isChildless());
    const huellen = blaetter.ancestors().union(bleibt.nodes().filter(n => n.isParent()));
    cy.batch(() => {
      cy.nodes().forEach(n => {
        if (bleibt.contains(n) || huellen.contains(n)) return;
        n.addClass(n.isParent() ? 'blassB' : 'blass');
      });
      cy.edges().not(bleibt.edges()).addClass('blass');
    });
  }

  const MAX_ZOOM_PASSEN = 1.3;
  // Einpassen ohne zu starke Vergrößerung bei wenigen Knoten.
  function ziel(eles, padding) {
    const bb = eles.boundingBox();
    const w = Math.max(1, cy.width() - 2 * padding), h = Math.max(1, cy.height() - 2 * padding);
    const zoom = Math.min(MAX_ZOOM_PASSEN, w / Math.max(1, bb.w), h / Math.max(1, bb.h));
    return { zoom, pan: { x: cy.width() / 2 - zoom * (bb.x1 + bb.w / 2), y: cy.height() / 2 - zoom * (bb.y1 + bb.h / 2) } };
  }
  function einpassen(eles, padding) { if (eles.nonempty()) cy.viewport(ziel(eles, padding)); }
  function fahre(v) {
    cy.stop(true, true);
    if (ruhig()) cy.viewport(v); else cy.animate(Object.assign(v, { duration: 300 }));
  }
  function passen(eles, padding) { if (eles.nonempty()) fahre(ziel(eles, padding)); }

  // Fokus-Zoom: Passen gewählter Knoten und direkte Nachbarn nur unter MIN_ZOOM_FOKUS ins Bild,
  // steht der gewählte Knoten bei MIN_ZOOM_FOKUS in der Mitte; die Nachbarn nennen Seitenleiste und
  // Zählzeile. MIN_ZOOM_FOKUS ist der Zoom, bei dem Dateinamen mindestens 11 px hoch erscheinen:
  // 11 / SCHRIFT_DATEI = 11 / 11,5 ≈ 0,957 (seit A06; vorher fest 0,6, Dateinamen nur etwa 7 px).
  // Ist ein gewählter Behälter selbst dabei zu groß, gilt der Zoom, der ihn ganz zeigt.
  const LESBAR_PX_FOKUS = 11;
  const MIN_ZOOM_FOKUS = LESBAR_PX_FOKUS / SCHRIFT_DATEI;
  function fokusZiel(gewaehlt, umgebung, padding) {
    const v = ziel(umgebung, padding);
    if (v.zoom >= MIN_ZOOM_FOKUS) return v;
    const zoom = Math.min(MIN_ZOOM_FOKUS, ziel(gewaehlt, padding).zoom);
    const bb = gewaehlt.boundingBox();
    return { zoom, pan: { x: cy.width() / 2 - zoom * (bb.x1 + bb.w / 2), y: cy.height() / 2 - zoom * (bb.y1 + bb.h / 2) } };
  }

  // Abgestufter Fokus auf Knoten (bei Behältern: ihr Inhalt). Gewählt voll, direkte Nachbarn n1,
  // zwei Verbindungen entfernt n2, Rest blass. Kanten bekommen die Stufe ihres blasseren Endes.
  function fokus(ids, opt) {
    leeren();
    const gewaehlt = cy.collection(ids.map(id => cy.getElementById(id)).filter(n => n.nonempty()));
    if (gewaehlt.empty()) return null;
    let kern = cy.collection();
    gewaehlt.forEach(n => { kern = kern.union(blattVon(n)); });
    const imKern = n => kern.contains(n);
    const e1 = kern.connectedEdges();
    const n1 = e1.connectedNodes().not(kern);
    const e2 = n1.connectedEdges().not(e1);
    const n2 = e2.connectedNodes().not(kern).not(n1);
    const stufe = n => imKern(n) ? 0 : n1.contains(n) ? 1 : n2.contains(n) ? 2 : 3;
    cy.batch(() => {
      abblenden(kern.union(n1).union(n2).union(gewaehlt));
      n1.addClass('n1'); n2.addClass('n2');
      e1.union(e2).forEach(e => {
        const s = Math.max(stufe(e.source()), stufe(e.target()));
        e.removeClass('blass');
        if (s === 1 && (imKern(e.source()) || imKern(e.target()))) e.addClass('hl');
        else if (s === 0) e.addClass('hl');
        else e.addClass(s === 1 ? 'n1' : s === 2 ? 'n2' : 'blass');
      });
      kern.addClass('hl');
      gewaehlt.addClass('gewaehlt');
    });
    // Fluss: Stufe 1 die direkten Kanten, Stufe 2 nur Ketten durch den gewählten Knoten.
    const rein1 = e1.filter(e => imKern(e.target()) && !imKern(e.source()));
    const raus1 = e1.filter(e => imKern(e.source()) && !imKern(e.target()));
    const rein2 = rein1.sources().incomers('edge').filter(e => !imKern(e.source())).not(e1);
    const raus2 = raus1.targets().outgoers('edge').filter(e => !imKern(e.target())).not(e1);
    rein1.union(rein2).addClass('rein');
    raus1.union(raus2).addClass('raus');
    if (!opt || !opt.ohneFluss) fluss.start(rein1.union(raus1), rein2.union(raus2));
    const nutzer = rein1.sources(), basis = raus1.targets();
    const nutzer2 = rein2.sources().not(kern).not(nutzer), basis2 = raus2.targets().not(kern).not(basis);
    const wer = opt && opt.titel ? opt.titel : name(gewaehlt[0].data('ref') || gewaehlt[0].id());
    if (!opt || !opt.ohneZeile) {
      pfadinfo.innerHTML = `<span class="m-rein">■</span> wer ${esc(wer)} nutzt: ${nutzer.length} direkt, ${nutzer2.length} eine Stufe weiter · <span class="m-raus">■</span> worauf ${esc(wer)} baut: ${basis.length} direkt, ${basis2.length} eine Stufe weiter`;
      pfadinfo.hidden = false;
    }
    if (!opt || !opt.ohneZoom) fahre(fokusZiel(gewaehlt, gewaehlt.union(kern).union(n1), 60));
    return { kern, n1, n2, e1, e2 };
  }

  function hebeKnotenHervor(id) {
    const c = sichtbarerKnoten(id);
    if (c) fokus([c], c !== id ? { titel: name(id) } : undefined);
    else leeren();
  }

  function hebeKanteHervor(e) {
    const ids = [e.source().id(), e.target().id()];
    // Fokus der beiden Enden ohne Animation; nur die gewählte Kante fließt, dicker und voll sichtbar.
    fokus(ids, { titel: name(e.source().data('ref') || ids[0]) + ' und ' + name(e.target().data('ref') || ids[1]), ohneZeile: true, ohneZoom: true, ohneFluss: true });
    // Ohne hl, sonst gewinnt bei Zyklus-Kanten die rote, schmalere Regel edge.zyk.hl.
    e.removeClass('blass n1 n2 hl rein raus').addClass('kgewaehlt');
    // Gehört sie zu einem Zyklus dieser Ansicht, bleiben dessen übrige Kanten rot, aber still.
    if (zustand.zyklen) {
      const zyk = zyklusKanten();
      const ringIds = new Set();
      e.data('kanten').forEach(id => (zyklenVonKante.get(id) || []).forEach(b => {
        if (b.beleg.kanten.some(k => zyk.has(k))) b.beleg.kanten.forEach(k => ringIds.add(k));
      }));
      if (ringIds.size) kantenMit([...ringIds]).not(e).removeClass('blass n1 n2 hl rein raus');
    }
    fluss.start(e);
    passen(e.union(e.connectedNodes()), 80);
    pfadinfo.textContent = name(e.source().data('ref') || ids[0]) + ' → ' + name(e.target().data('ref') || ids[1]) + ' · ' + kurzArt(e.data('art')) + ' · Gewicht ' + e.data('gewicht');
    pfadinfo.hidden = false;
  }

  function hebeZyklusHervor(b) {
    leeren();
    const mitglieder = cy.collection(b.beleg.knoten.map(id => cy.getElementById(id)).filter(e => e.nonempty()));
    const ring = kantenMit(b.beleg.kanten);
    const einstiege = new Set(b.beleg.einstiege.map(e => e.knoten));
    const quellen = new Set(b.beleg.einstiege.flatMap(e => e.quellen));
    const rein = cy.edges().filter(e => einstiege.has(e.target().id()) && !ring.contains(e) &&
      e.data('kanten').some(id => { const k = kanteNachId.get(id); return k && quellen.has(k.von); }));
    abblenden(mitglieder.union(ring).union(rein).union(rein.sources()));
    mitglieder.addClass('hl');
    ring.addClass('hl');
    mitglieder.filter(n => einstiege.has(n.id())).addClass('einstieg');
    rein.addClass('einstieg');
    const trennIds = b.beleg.trennstelle ? [b.beleg.trennstelle] : (b.beleg.kleinste_trennmenge || []);
    const trenn = kantenMit(trennIds).filter(e => ring.contains(e));
    trenn.addClass('trenn').data('trennText', b.beleg.trennstelle ? 'günstigste Trennstelle' : 'kleinste Trennmenge');
    // Der Fluss läuft endlos im Ring.
    fluss.start(ring);
    const teile = [befundTitel(b)];
    if (b.beleg.einstiege.length) teile.push('Einstieg: ' + b.beleg.einstiege.map(e => name(e.knoten) + ' (von ' + e.quellen.map(name).join(', ') + ')').join('; '));
    if (b.beleg.trennstelle) teile.push('günstigste Trennstelle: ' + kanteText(b.beleg.trennstelle));
    else if (b.beleg.kleinste_trennmenge) teile.push('kleinste Trennmenge: ' + b.beleg.kleinste_trennmenge.map(kanteText).join(', '));
    pfadinfo.textContent = teile.join(' · ');
    pfadinfo.hidden = false;
    passen(mitglieder.union(ring), 70);
  }
  function kanteText(id) {
    const k = kanteNachId.get(id);
    return k ? name(k.von) + ' → ' + name(k.nach) + ' (Gewicht ' + k.gewicht + ')' : id;
  }

  // Knoten-Id der Messung → Id des Knotens, der ihn auf der aktuellen Karte vertritt.
  function sichtbarerKnoten(id) {
    if (cy.getElementById(id).nonempty()) return id;
    const k = knoten.get(id);
    if (!k) return null;
    if (inSammel.has(id) && cy.getElementById(SAMMEL).nonempty()) return SAMMEL;
    if (k.art === 'datei') {
      const g = behaelter(k);
      if (k.fremd && cy.getElementById('fremd:' + g).nonempty()) return 'fremd:' + g;
      if (cy.getElementById(g).nonempty()) return g;
    }
    return null;
  }

  // ------------------------------------------------------------ 7. Seitenleiste
  const seite = document.getElementById('seite');
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const EBENEN_TEXT = { datei: 'Dateien', paket: 'Paketen', modul: 'Modulen' };
  const zahl = v => v === null || v === undefined ? '–' : String(v).replace('.', ',');
  const kn = id => knoten.has(id) || id === SAMMEL ? `<button type="button" class="zur" data-knoten="${esc(id)}">${esc(name(id))}</button>` : `<code>${esc(name(id))}</code>`;
  const kk = (id, text) => `<button type="button" class="zur" data-kante="${esc(id)}">${esc(text)}</button>`;

  function befundTitel(b) {
    const beleg = b.beleg;
    if (b.regel === 'zyklus') {
      let t = 'Zyklus aus ' + beleg.knoten.length + ' ' + EBENEN_TEXT[beleg.ebene];
      if (beleg.kantenart) t += ' (' + beleg.kantenart + ')';
      return t + (beleg.rolle === 'mit-tests' ? ' mit Tests' : '');
    }
    if (b.regel === 'jni-ohne-gegenstueck') return 'JNI ohne Gegenstück';
    if (b.regel === 'unaufgeloest') return beleg.importe.length + ' unaufgelöste Importe';
    if (istMarkierung(b)) return kurzFunktion(beleg.von) + ' ruft unmarkiert ' + kurzFunktion(beleg.nach) + (beleg.kette.length ? ' (+' + beleg.kette.length + ')' : '') + (beleg.unsicher ? ' · unsicher' : '');
    if (istDetekt(b)) return 'detekt: ' + b.regel;
    return b.regel;
  }
  function befundBeleg(b) {
    if (b.regel === 'zyklus') return b.beleg.knoten.map(name).join(' · ');
    if (b.regel === 'jni-ohne-gegenstueck') return b.beleg.funktion + ' (' + (b.beleg.seite === 'c' ? 'C' : 'Kotlin') + ', Zeile ' + b.beleg.zeile + ')';
    if (b.regel === 'unaufgeloest') return name(b.knoten[0]) + ': ' + b.beleg.importe.map(i => i.import).join(', ');
    if (istMarkierung(b)) return b.beleg.markierung.name.split('.').pop() + ' (' + b.beleg.markierung.traeger + ') · ' + dateiDerFunktion(b.beleg.von).slice(6).split('/').pop() + ':' + b.beleg.zeilen.join(', ');
    if (istDetekt(b)) return name(dateiDerFunktion(b.knoten[0])) + ':' + b.beleg.zeile + ' · ' + b.beleg.meldung;
    return b.knoten.map(name).join(', ');
  }
  const farbe = b => b.regel === 'zyklus' || b.schwere === 'fehler' ? 'crit' : 'warn';

  function befundKnopf(b, nr) {
    const e = einschaetzung.get(b.id);
    const titel = e ? e.titel : befundTitel(b);
    const unter = e ? (e.vorschlag || e.begruendung) : '';
    const aktuell = zustand.auswahl && zustand.auswahl.art === 'befund' && zustand.auswahl.id === b.id;
    // Einschätzung ohne Priorität: gedämpftes Zeichen „nachrangig“ statt einer Zahl.
    const nachrangig = e && e.prioritaet == null;
    const prio = nr === null
      ? '<span class="prio nachrangig" aria-hidden="true"></span>'
      : `<span class="prio ${farbe(b)}">${esc(nr)}</span>`;
    const marke = nachrangig ? ' <span class="nachrangig-marke">nachrangig</span>' : '';
    return `<li><button type="button" data-befund="${esc(b.id)}"${aktuell ? ' aria-current="true"' : ''}>${prio}<span class="bt">${esc(titel)}${marke}</span><span class="bm">${esc(befundBeleg(b))}</span>${unter ? `<span class="bd">${esc(unter)}</span>` : '<span></span>'}</button></li>`;
  }

  function sortierteBefunde() {
    const mitDeutung = D.einschaetzungen.map(e => befundNachId.get(e.befund)).filter(b => b && befundSichtbar(b));
    const rest = M.befunde.filter(b => !einschaetzung.has(b.id) && befundSichtbar(b));
    const rang = { zyklus: 0, 'markierung-verlassen': 1, 'jni-ohne-gegenstueck': 2, unaufgeloest: 3 };
    const rangVon = b => istDetekt(b) ? 5 : rang[b.regel] ?? 4;
    rest.sort((a, b) => rangVon(a) - rangVon(b) ||
      (istMarkierung(a) && istMarkierung(b) ? b.beleg.anzahl - a.beleg.anzahl : 0) ||
      (b.regel === 'zyklus' ? b.knoten.length - a.knoten.length : 0) || (a.id < b.id ? -1 : 1));
    return { mitDeutung, rest };
  }

  function uebersicht() {
    const { mitDeutung, rest } = sortierteBefunde();
    const zaehle = art => M.knoten.filter(k => k.art === art).length;
    const dateienAlle = M.knoten.filter(k => k.art === 'datei');
    const zyklen = { datei: 0, paket: 0, modul: 0 };
    M.befunde.forEach(b => { if (b.regel === 'zyklus') zyklen[b.beleg.ebene]++; });
    let html = `<div><h2>Überblick</h2><p class="leer">Klick auf einen Befund hebt ihn hervor, Klick auf einen Knoten oder eine Verbindung zeigt Details. Doppelklick wechselt in die nächste Ebene${gross ? ' bzw. klappt auf der Dateiebene ein Modul aus oder ein' : ''}. Schlösser oben rechts an jedem Kasten geben ihn zum Verschieben frei.</p></div>`;
    if (mitDeutung.length) {
      html += `<div><h3 class="quelle-d">Befunde, gewichtet <em>gedeutet · deutung.json</em></h3><ol class="befunde">${mitDeutung.map(b => befundKnopf(b, einschaetzung.get(b.id).prioritaet ?? null)).join('')}</ol></div>`;
    }
    html += `<div><h3 class="quelle-m">Befunde <em>gemessen · daidalos.json</em></h3>${rest.length ? `<ol class="befunde">${rest.map(b => befundKnopf(b, b.regel === 'zyklus' ? b.knoten.length : '!')).join('')}</ol>` : '<p class="leer">Keine Befunde.</p>'}</div>`;
    html += `<div><h3 class="quelle-m">Auf einen Blick <em>gemessen · daidalos.json</em></h3><table>
      <tr><td>Module · Ordner · Pakete</td><td>${zaehle('modul')} · ${zaehle('ordner')} · ${zaehle('paket')}</td></tr>
      <tr><td>Dateien (fremd)</td><td>${dateienAlle.length} (${dateienAlle.filter(d => d.fremd).length})</td></tr>
      <tr><td>Zeilen</td><td>${dateienAlle.reduce((s, d) => s + (d.zeilen || 0), 0)}</td></tr>
      <tr><td>nutzt-Kanten zwischen Dateien (unsicher)</td><td>${dateiKanten.length} (${dateiKanten.filter(k => !k.sicher).length})</td></tr>
      <tr><td>Gradle-Kanten</td><td>${M.kanten.filter(k => k.art.startsWith('gradle-')).length}</td></tr>
      <tr><td>JNI-Paare</td><td>${M.kanten.filter(k => k.art === 'jni').reduce((s, k) => s + k.gewicht, 0)}</td></tr>
      <tr><td>Zyklen Datei · Paket · Modul</td><td>${zyklen.datei} · ${zyklen.paket} · ${zyklen.modul}</td></tr>
    </table></div>`;
    if (D.bereiche.length) {
      html += `<div><h3 class="quelle-d">Bereiche <em>gedeutet · deutung.json</em></h3>${D.bereiche.map(b => `<div class="bereich"><p><b>${esc(b.name)}</b></p>${b.beschreibung ? `<p class="deut">${esc(b.beschreibung)}</p>` : ''}<p class="pfad">${b.knoten.map(kn).join(' · ')}</p></div>`).join('')}</div>`;
    }
    seite.innerHTML = html;
    verdrahte();
  }

  function beschreibungHtml(id) {
    const b = D.beschreibungen[id];
    if (!b) return `<div><h3 class="quelle-d">Beschreibung <em>gedeutet · deutung.json</em></h3><p class="leer">Noch keine Beschreibung.</p></div>`;
    return `<div><h3 class="quelle-d">Beschreibung <em>gedeutet · deutung.json</em></h3><p class="deut">${esc(b.text)}</p>${b.veraltet ? '<div class="chips" style="margin-top:6px"><span class="chip warn" title="Der Knoten hat sich seit der Deutung geändert">veraltet</span></div>' : ''}</div>`;
  }

  function verbindungen(id) {
    const k = knoten.get(id);
    const passt = e => (e.art === 'nutzt' || e.art === 'jni' || e.art.startsWith('gradle-')) && rolleOk(e);
    const fmt = (e, gegen) => `<li>${kn(gegen)} <span class="leer">${kk(e.id, kurzArt(e.art))} · Gewicht ${e.gewicht}${e.sicher === false ? ' · unsicher' : ''}${e.rolle === 'test' ? ' · Test' : ''}</span></li>`;
    const sortiere = (a, b) => b.gewicht - a.gewicht || (a.id < b.id ? -1 : 1);
    const raus = M.kanten.filter(e => e.von === id && passt(e)).sort(sortiere);
    const rein = M.kanten.filter(e => e.nach === id && passt(e)).sort(sortiere);
    const hinweis = k.art === 'datei' ? '' : ' (verdichtet)';
    return `<div><h3 class="quelle-m">Nutzt${hinweis} <em>${raus.length}</em></h3>${raus.length ? '<ul class="liste">' + raus.map(e => fmt(e, e.nach)).join('') + '</ul>' : '<p class="leer">nichts</p>'}</div>
      <div><h3 class="quelle-m">Wird genutzt von${hinweis} <em>${rein.length}</em></h3>${rein.length ? '<ul class="liste">' + rein.map(e => fmt(e, e.von)).join('') + '</ul>' : '<p class="leer">niemandem</p>'}</div>`;
  }

  function sammelDetails() {
    const dateienVon = g => M.knoten.filter(d => d.art === 'datei' && d.ordner === g.id).sort((a, b) => a.pfad < b.pfad ? -1 : 1);
    seite.innerHTML = `<button type="button" class="zur" data-zurueck>← Übersicht</button>
      <div><h2>Weitere Ordner</h2><p class="pfad">Ordner außerhalb der Module, ohne Quellcode auf der Karte und ohne Kanten</p></div>
      <div><h3 class="quelle-m">Ordner <em>${weitereOrdner.length}</em></h3>${weitereOrdner.map(g => {
        const ds = dateienVon(g);
        return `<details class="ordner"><summary><code>${esc(name(g.id))}</code> <span class="leer">${g.dateien || 0} Dateien · ${g.zeilen || 0} Zeilen</span></summary><ul class="liste">${ds.map(d => `<li><code>${esc(d.pfad)}</code> <span class="leer">${d.zeilen ?? '–'} Zeilen</span> ${editorKnopf(d.pfad, 1, true)}</li>`).join('')}</ul></details>`;
      }).join('')}</div>`;
    verdrahte();
  }

  function knotenDetails(id) {
    if (id === SAMMEL) { sammelDetails(); return; }
    const k = knoten.get(id);
    if (!k) { uebersicht(); return; }
    let unter = '';
    if (k.art === 'datei') unter = k.pfad;
    else if (k.art === 'modul') unter = 'Gradle-Modul · ' + k.pfad + '/';
    else if (k.art === 'paket') unter = 'Paket in ' + name(k.modul || k.ordner);
    else unter = 'Ordner außerhalb der Module';
    const chips = [];
    if (k.sprache) chips.push(`<span class="chip">${esc(k.sprache)}</span>`);
    if (k.rolle === 'test') chips.push('<span class="chip warn">Test</span>');
    if (k.quellsatz) chips.push(`<span class="chip">${esc(k.quellsatz)}</span>`);
    if (k.fremd) chips.push('<span class="chip adr">fremd</span>');
    const m = k.metriken || {};
    const zeilen = [];
    if (k.zeilen !== undefined) zeilen.push(['Zeilen', k.zeilen]);
    if (k.dateien !== undefined) zeilen.push(['Dateien (eigene)', k.dateien]);
    zeilen.push(['Fan-in · Fan-out', zahl(m.fan_in) + ' · ' + zahl(m.fan_out)]);
    zeilen.push(['Instabilität', zahl(m.instabilitaet)]);
    const bf = M.befunde.filter(b => befundSichtbar(b) && b.knoten.some(x => x === id || dateiDerFunktion(x) === id));
    const mitFunktionen = k.art === 'datei' && (k.sprache === 'kotlin' || k.sprache === 'c');
    const symbole = k.art === 'datei' ? `<div class="symbole"><button type="button" disabled title="Code-Ansicht kommt mit daidalos serve">${SVG_CODE}Code</button>${editorKnopf(k.pfad, 1)}${mitFunktionen ? `<button type="button" data-funktionen-datei="${esc(k.pfad)}" title="Funktionsebene dieser Datei öffnen">Funktionen</button>` : ''}</div>` : '';
    seite.innerHTML = `<button type="button" class="zur" data-zurueck>← Übersicht</button>
      <div><div class="kopfzeile"><h2>${esc(name(id))}</h2>${symbole}</div><p class="pfad">${esc(unter)}</p>${chips.length ? `<div class="chips" style="margin-top:6px">${chips.join('')}</div>` : ''}</div>
      ${beschreibungHtml(id)}
      <div><h3 class="quelle-m">Messwerte <em>gemessen · daidalos.json</em></h3><table>${zeilen.map(([a, b]) => `<tr><td>${esc(a)}</td><td>${esc(b)}</td></tr>`).join('')}</table></div>
      ${verbindungen(id)}
      ${bf.length ? `<div><h3 class="quelle-m">Befunde an diesem Knoten <em>${bf.length}</em></h3><ol class="befunde">${bf.map(b => befundKnopf(b, b.regel === 'zyklus' ? b.knoten.length : '!')).join('')}</ol></div>` : ''}`;
    verdrahte();
  }

  function befundDetails(b) {
    const e = einschaetzung.get(b.id);
    let html = `<button type="button" class="zur" data-zurueck>← Übersicht</button><div><h2>${esc(e ? e.titel : befundTitel(b))}</h2><p class="pfad">${esc(b.id)}</p></div>`;
    if (e) {
      html += `<div><h3 class="quelle-d">Einschätzung <em>gedeutet · deutung.json</em></h3><div class="deut">${e.prioritaet != null ? `<p><b>Priorität ${esc(e.prioritaet)}</b></p>` : '<p><span class="nachrangig-marke">nachrangig</span></p>'}${e.begruendung ? `<p>${esc(e.begruendung)}</p>` : ''}${e.vorschlag ? `<p style="margin-top:6px"><b>Vorschlag:</b> ${esc(e.vorschlag)}</p>` : ''}</div></div>`;
    }
    const beleg = b.beleg;
    let mess = '';
    if (b.regel === 'zyklus') {
      mess += `<table><tr><td>Ebene</td><td>${esc(beleg.ebene)}${beleg.kantenart ? ' · ' + esc(beleg.kantenart) : ''}</td></tr><tr><td>Rolle</td><td>${esc(beleg.rolle)}</td></tr><tr><td>Kanten im Zyklus</td><td>${beleg.kanten.length}</td></tr><tr><td>Kanten, deren Wegfall allein ihn löst</td><td>${(beleg.loesende_kanten || []).length}</td></tr><tr><td>unsichere Kante beteiligt</td><td>${beleg.unsicher ? 'ja' : 'nein'}</td></tr></table>`;
      mess += `<p style="margin-top:8px"><b>Mitglieder</b></p><ul class="liste">${beleg.knoten.map(id => `<li>${kn(id)}</li>`).join('')}</ul>`;
      mess += `<p style="margin-top:8px"><b>Einstiege</b></p>${beleg.einstiege.length ? `<ul class="liste">${beleg.einstiege.map(x => `<li>${kn(x.knoten)} <span class="leer">von ${x.quellen.map(kn).join(', ')}</span></li>`).join('')}</ul>` : '<p class="leer">keine</p>'}`;
      mess += `<p style="margin-top:8px"><b>Trennstelle</b></p>${beleg.trennstelle ? `<p>günstigste Trennstelle: ${kk(beleg.trennstelle, kanteText(beleg.trennstelle))}</p>` : beleg.kleinste_trennmenge ? `<p>keine einzelne; kleinste Trennmenge: ${beleg.kleinste_trennmenge.map(id => kk(id, kanteText(id))).join(', ')}</p>` : '<p class="leer">keine einzelne Trennstelle</p>'}`;
      if ((beleg.loesende_kanten || []).length > 1) mess += `<p style="margin-top:8px"><b>Ebenfalls lösend</b></p><ul class="liste">${beleg.loesende_kanten.filter(id => id !== beleg.trennstelle).map(id => `<li>${kk(id, kanteText(id))}</li>`).join('')}</ul>`;
      if (beleg.enthaelt_produktiv) mess += `<p style="margin-top:8px">Enthält ${beleg.enthaelt_produktiv.length} produktive Zyklen.</p>`;
    } else if (b.regel === 'jni-ohne-gegenstueck') {
      const d = knoten.get(b.knoten[0]);
      mess += `<table><tr><td>Funktion</td><td>${esc(beleg.funktion)}</td></tr><tr><td>Seite</td><td>${beleg.seite === 'c' ? 'C/C++' : 'Kotlin'}</td></tr><tr><td>Datei</td><td>${kn(b.knoten[0])}</td></tr><tr><td>Zeile</td><td>${beleg.zeile} ${d ? editorKnopf(d.pfad, beleg.zeile, true) : ''}</td></tr></table>`;
    } else if (istMarkierung(b)) {
      mess += `<p style="margin-bottom:8px"><button type="button" class="btn" data-grenze="${esc(b.id)}">Auf Funktionsebene zeigen</button></p>`;
      mess += markierungsBeleg(b);
    } else if (istDetekt(b)) {
      if (b.knoten[0].startsWith('funktion:')) mess += `<p style="margin-bottom:8px"><button type="button" class="btn" data-funktion="${esc(b.knoten[0])}">Auf Funktionsebene zeigen</button></p>`;
      const pfad = dateiDerFunktion(b.knoten[0]).slice(6);
      const quellen = Array.isArray(beleg.sarif) ? beleg.sarif : [beleg.sarif];
      mess += `<table class="kettenbeleg"><tr><td>Regel</td><td>${esc(b.regel)}</td></tr><tr><td>Schwere</td><td>${esc(b.schwere)}</td></tr><tr><td>Ort</td><td>${kn('datei:' + pfad)}:${beleg.zeile} ${editorKnopf(pfad, beleg.zeile, true)}</td></tr>${b.knoten[0].startsWith('funktion:') ? `<tr><td>Funktion</td><td><code>${esc(kurzFunktion(b.knoten[0]))}</code></td></tr>` : ''}<tr><td>SARIF</td><td>${quellen.map(q => `<code>${esc(q)}</code>`).join('<br>')}</td></tr></table><p style="margin-top:8px">${esc(beleg.meldung)}</p>`;
    } else if (b.regel === 'unaufgeloest') {
      const d = knoten.get(b.knoten[0]);
      mess += `<p>${kn(b.knoten[0])}</p><ul class="liste">${beleg.importe.map(i => `<li><code>${esc(i.import)}</code> <span class="leer">Zeile ${i.zeile}</span> ${d ? editorKnopf(d.pfad, i.zeile, true) : ''}</li>`).join('')}</ul>`;
    }
    html += `<div><h3 class="quelle-m">Beleg <em>gemessen · daidalos.json</em></h3><div class="mess">${mess}</div></div>`;
    seite.innerHTML = html;
    verdrahte();
  }

  // Eine Funktion der Kette: Name, Datei:Zeile, Editor-Link.
  function funktionsZeile(id, zeile, zusatz) {
    const pfad = dateiDerFunktion(id).slice(6);
    return `<button type="button" class="zur" data-funktion="${esc(id)}"><code>${esc(kurzFunktion(id))}</code></button> <span class="ort">${esc(pfad.split('/').pop())}:${zeile}</span> ${editorKnopf(pfad, zeile, true)}${zusatz ? ` <span class="leer">${esc(zusatz)}</span>` : ''}`;
  }
  // Kette als eingerückte Liste: jede Funktion unter ihrem Aufrufer (Vorgänger im kürzesten Weg).
  function ketteHtml(wurzel, wurzelZeile, eintraege, mitWurzel) {
    const kinder = new Map();
    eintraege.forEach(e => { if (!kinder.has(e.von)) kinder.set(e.von, []); kinder.get(e.von).push(e); });
    const zeilen = [];
    const gezeigt = new Set();
    const gehe = (id, zeile, tiefe, zusatz) => {
      gezeigt.add(id);
      zeilen.push(`<li style="padding-left:${tiefe * 14}px">${tiefe ? '↳ ' : ''}${funktionsZeile(id, zeile, zusatz)}</li>`);
      (kinder.get(id) || []).forEach(e => gehe(e.funktion, e.zeile, tiefe + 1, e.schritt ? 'über ' + kurzFunktion(e.ueber) + ' (' + e.schritt + ')' : ''));
    };
    if (mitWurzel) gehe(wurzel, wurzelZeile, 0, '');
    else (kinder.get(wurzel) || []).forEach(e => gehe(e.funktion, e.zeile, 0, ''));
    // Einträge, deren Aufrufer nicht in dieser Liste steht (kette_unsicher hängt an der sicheren Kette)
    eintraege.filter(e => !gezeigt.has(e.funktion)).forEach(e => gehe(e.funktion, e.zeile, 0, 'aufgerufen von ' + kurzFunktion(e.von)));
    const liste = `<ul class="liste kette">${zeilen.join('')}</ul>`;
    return eintraege.length > 30 ? `<details><summary>${zeilen.length} Funktionen zeigen</summary>${liste}</details>` : liste;
  }
  function markierungsBeleg(b) {
    const beleg = b.beleg;
    let mess = `<table class="kettenbeleg"><tr><td>markiert</td><td>${funktionsZeile(beleg.von, beleg.von_zeile)}</td></tr><tr><td>Markierung</td><td><code>${esc(beleg.markierung.name)}</code> an ${esc({ funktion: 'der Funktion', klasse: 'der Klasse', datei: 'der Datei' }[beleg.markierung.traeger])}</td></tr><tr><td>Aufrufstellen</td><td>Zeile ${beleg.zeilen.join(', ')}</td></tr><tr><td>Länge der Kette</td><td>${beleg.anzahl}</td></tr><tr><td>über ueberschreibt/actual</td><td>${beleg.ueber_ueberschreiben ? 'ja' : 'nein'}</td></tr><tr><td>nur unsicher</td><td>${beleg.unsicher ? 'ja' : 'nein'}</td></tr>${beleg.delegiert_gelesen ? `<tr><td>delegierte Eigenschaften gelesen</td><td>${beleg.delegiert_gelesen}</td></tr>` : ''}</table>`;
    mess += `<p style="margin-top:8px"><b>Unmarkiert erreicht</b> <span class="leer">${beleg.anzahl}</span></p>${ketteHtml(beleg.nach, beleg.nach_zeile, beleg.kette, true)}`;
    if (beleg.kette_unsicher) mess += `<p style="margin-top:8px"><b>Zusätzlich nur über unsichere Kanten</b> <span class="leer">${beleg.kette_unsicher.length}</span></p>${ketteHtml(beleg.nach, beleg.nach_zeile, beleg.kette_unsicher, false)}`;
    if (beleg.ausnahmen.length) mess += `<p style="margin-top:8px"><b>Endet an Ausnahmen</b></p><ul class="liste">${beleg.ausnahmen.map(id => `<li><code>${esc(kurzFunktion(id))}</code></li>`).join('')}</ul>`;
    return mess;
  }

  // ---- Kanten-Details
  const gruppeVon = id => { const k = knoten.get(id); return !k ? null : k.art === 'datei' || k.art === 'paket' ? (k.modul || k.ordner) : k.id; };
  const ROLLE_TEXT = { produktiv: 'produktiv', test: 'Test' };

  // Datei-Kanten, die eine verdichtete Paket- oder Modul-Kante tragen.
  function tragende(k) {
    if (k.von.startsWith('datei:')) return [k];
    const zu = k.von.startsWith('paket:') ? (d => d.paket) : behaelter;
    return dateiKanten.filter(x => x.rolle === k.rolle && zu(knoten.get(x.von)) === k.von && zu(knoten.get(x.nach)) === k.nach);
  }
  // Datei-Kanten, die eine Gradle-Abhängigkeit tatsächlich verwenden.
  function nutzerVonGradle(k) {
    return dateiKanten.filter(x => rolleOk(x) && behaelter(knoten.get(x.von)) === k.von && behaelter(knoten.get(x.nach)) === k.nach);
  }

  function grenze(k) {
    const a = knoten.get(k.von), b = knoten.get(k.nach);
    if (!a || !b) return null;
    const ga = gruppeVon(k.von), gb = gruppeVon(k.nach);
    const zeilen = [];
    if (a.art === 'datei' && b.art === 'datei') {
      if (ga !== gb) zeilen.push(['Grenze', 'über eine Modulgrenze (' + name(ga) + ' → ' + name(gb) + ')']);
      else if (a.paket !== b.paket) zeilen.push(['Grenze', 'zwischen Paketen desselben Moduls']);
      else zeilen.push(['Grenze', 'innerhalb eines Pakets']);
      if (k.art === 'nutzt' && a.paket && b.paket && a.paket !== b.paket) {
        const p = verdichtet.get(a.paket + '|' + b.paket + '|' + k.rolle);
        if (p) zeilen.push(['einzige Verbindung der beiden Pakete', p.dateikanten === 1 ? 'ja' : 'nein (' + p.dateikanten + ' Datei-Kanten)']);
      }
      if (k.art === 'nutzt' && ga !== gb) {
        const m = verdichtet.get(ga + '|' + gb + '|' + k.rolle);
        if (m) zeilen.push(['einzige Verbindung der beiden Module', m.dateikanten === 1 ? 'ja' : 'nein (' + m.dateikanten + ' Datei-Kanten)']);
      }
    } else if (a.art === 'paket' && b.art === 'paket') {
      zeilen.push(['Grenze', ga !== gb ? 'über eine Modulgrenze (' + name(ga) + ' → ' + name(gb) + ')' : 'zwischen Paketen desselben Moduls']);
      zeilen.push(['einzige Verbindung der beiden Pakete', k.dateikanten === 1 ? 'ja, eine Datei-Kante' : 'nein (' + k.dateikanten + ' Datei-Kanten)']);
      if (ga !== gb) {
        const zahlP = M.kanten.filter(x => x.art === 'nutzt' && x.rolle === k.rolle && x.von.startsWith('paket:') && gruppeVon(x.von) === ga && gruppeVon(x.nach) === gb).length;
        zeilen.push(['einzige Paket-Verbindung der beiden Module', zahlP === 1 ? 'ja' : 'nein (' + zahlP + ' Paket-Kanten)']);
      }
    } else {
      zeilen.push(['Grenze', 'über eine Modulgrenze']);
      if (k.art === 'nutzt') zeilen.push(['einzige Verbindung der beiden Module', k.dateikanten === 1 ? 'ja, eine Datei-Kante' : 'nein (' + k.dateikanten + ' Datei-Kanten)']);
    }
    return zeilen;
  }

  function belegeHtml(k) {
    const von = knoten.get(k.von), nach = knoten.get(k.nach);
    if (k.art === 'nutzt' && von && von.art === 'datei') {
      return `<table class="belege"><tr><th>Symbol</th><th>Zeile</th><th>Herkunft</th><th></th></tr>${k.beleg.map(b => `<tr><td><code>${esc(b.symbol)}</code></td><td>${b.zeile}</td><td>${esc(b.herkunft)}${b.sicher ? '' : ' · unsicher'}</td><td>${editorKnopf(von.pfad, b.zeile, true)}</td></tr>`).join('')}</table>`;
    }
    if (k.art === 'jni') {
      return `<table class="belege"><tr><th>Funktion</th><th>Kotlin</th><th>C</th></tr>${k.beleg.map(b => `<tr><td><code>${esc(b.funktion)}</code></td><td>${b.zeile_kotlin} ${editorKnopf(von.pfad, b.zeile_kotlin, true)}</td><td>${b.zeile_c} ${editorKnopf(nach.pfad, b.zeile_c, true)}</td></tr>`).join('')}</table>`;
    }
    if (k.art.startsWith('gradle-')) {
      return `<table class="belege"><tr><th>Build-Datei</th><th>Konfiguration</th><th>Quellsatz</th><th></th></tr>${k.beleg.map(b => `<tr><td><code>${esc(b.datei)}:${b.zeile}</code></td><td>${esc(b.konfiguration)}</td><td>${esc(b.quellsatz || '–')}${b.bedingt ? ' · bedingt' : ''}${b.quelle === 'wurzel' ? ' · aus der Wurzel' : ''}</td><td>${editorKnopf(b.datei, b.zeile, true)}</td></tr>`).join('')}</table>`;
    }
    return '';
  }

  function kantenListe(liste, leer) {
    if (!liste.length) return `<p class="leer">${esc(leer)}</p>`;
    const sortiert = liste.slice().sort((a, b) => b.gewicht - a.gewicht || (a.id < b.id ? -1 : 1));
    const zeig = sortiert.slice(0, 60);
    return `<ul class="liste">${zeig.map(x => `<li>${kk(x.id, name(x.von) + ' → ' + name(x.nach))} <span class="leer">Gewicht ${x.gewicht}${x.sicher === false ? ' · unsicher' : ''}</span></li>`).join('')}</ul>${sortiert.length > zeig.length ? `<p class="leer">… und ${sortiert.length - zeig.length} weitere</p>` : ''}`;
  }

  function kanteDetails(e) {
    const d = e.data();
    const ks = d.kanten.map(id => kanteNachId.get(id)).filter(Boolean);
    const einzeln = ks.length === 1 && !d.verdichtet ? ks[0] : null;
    const quelle = d.source, ziel = d.target;
    let html = `<button type="button" class="zur" data-zurueck>← Übersicht</button>
      <div><h2>${kn(e.source().data('ref') || quelle)} → ${kn(e.target().data('ref') || ziel)}</h2><p class="pfad">${esc(einzeln ? einzeln.id : 'verdichtet aus ' + ks.length + ' Kanten')}</p></div>`;
    const zeilen = [['Art', d.art + (d.verdichtet ? ' (verdichtet)' : '')], ['Gewicht', d.gewicht]];
    if (einzeln) {
      zeilen.push(['Rolle', ROLLE_TEXT[einzeln.rolle] || einzeln.rolle || '–']);
      zeilen.push(['sicher', einzeln.sicher === false ? 'unsicher' : 'sicher']);
      if (einzeln.dateikanten !== undefined) zeilen.push(['Datei-Kanten darunter', einzeln.dateikanten]);
      (grenze(einzeln) || []).forEach(z => zeilen.push(z));
    } else {
      zeilen.push(['Rolle', [...new Set(ks.map(k => ROLLE_TEXT[k.rolle] || k.rolle))].join(', ')]);
      zeilen.push(['sicher', d.unsicher ? 'unsicher' : 'sicher']);
      zeilen.push(['Grenze', 'eingeklappt: ' + name(e.source().data('ref') || quelle) + ' → ' + name(e.target().data('ref') || ziel)]);
    }
    html += `<div><h3 class="quelle-m">Verbindung <em>gemessen · daidalos.json</em></h3><table>${zeilen.map(([a, b]) => `<tr><td>${esc(a)}</td><td>${esc(b)}</td></tr>`).join('')}</table></div>`;
    // Zyklus-Bezug
    const zyk = [];
    ks.forEach(k => (zyklenVonKante.get(k.id) || []).forEach(b => { if (!zyk.some(z => z.b === b && z.k === k)) zyk.push({ b, k }); }));
    if (zyk.length) {
      html += `<div><h3 class="quelle-m">Zyklus <em>${zyk.length}</em></h3><ul class="liste">${zyk.map(({ b, k }) => `<li><button type="button" class="zur" data-befund="${esc(b.id)}">${esc(befundTitel(b))}</button><br><span class="leer">${ks.length > 1 ? esc(name(k.von) + ' → ' + name(k.nach)) + ': ' : ''}${b.beleg.trennstelle === k.id ? 'günstigste Trennstelle' : 'nicht die günstigste Trennstelle'} · Wegfall allein ${(b.beleg.loesende_kanten || []).includes(k.id) ? 'löst den Zyklus' : 'löst ihn nicht'}</span></li>`).join('')}</ul></div>`;
    }
    if (einzeln && (einzeln.beleg || []).length) {
      html += `<div><h3 class="quelle-m">Belege <em>${einzeln.beleg.length}</em></h3>${belegeHtml(einzeln)}</div>`;
    }
    // Tragende Datei-Kanten bei verdichteten Kanten
    let traeger = [];
    ks.forEach(k => { if (k.art === 'nutzt') traeger = traeger.concat(tragende(k)); });
    if (ks.some(k => k.art === 'nutzt' && !k.von.startsWith('datei:'))) {
      html += `<div><h3 class="quelle-m">Getragen von <em>${traeger.length} Datei-Kanten</em></h3>${kantenListe(traeger, 'keine Datei-Kanten')}</div>`;
    }
    ks.filter(k => k.art.startsWith('gradle-')).forEach(k => {
      html += `<div><h3 class="quelle-m">Verwendet von <em>${nutzerVonGradle(k).length} Datei-Kanten</em></h3>${kantenListe(nutzerVonGradle(k), 'keine nutzt-Kante verwendet diese Abhängigkeit')}</div>`;
    });
    if (ks.length > 1 && ks.every(k => k.von.startsWith('datei:'))) {
      html += `<div><h3 class="quelle-m">Kanten darunter <em>${ks.length}</em></h3>${kantenListe(ks, '')}</div>`;
    }
    ks.forEach(k => {
      const t = D.kanten[k.id];
      if (t) html += `<div><h3 class="quelle-d">Deutung <em>gedeutet · deutung.json</em></h3><p class="deut">${esc(t.text)}</p></div>`;
    });
    seite.innerHTML = html;
    verdrahte();
  }

  function verdrahte() {
    seite.querySelectorAll('[data-befund]').forEach(b => b.addEventListener('click', () => zeigeBefund(b.dataset.befund)));
    seite.querySelectorAll('[data-knoten]').forEach(b => b.addEventListener('click', () => zeigeKnoten(b.dataset.knoten)));
    seite.querySelectorAll('[data-kante]').forEach(b => b.addEventListener('click', () => zeigeKante(b.dataset.kante)));
    seite.querySelectorAll('[data-funktion]').forEach(b => b.addEventListener('click', () => zeigeFunktion(b.dataset.funktion)));
    seite.querySelectorAll('[data-funktionen-datei]').forEach(b => b.addEventListener('click', () => zeigeFunktionsDatei(b.dataset.funktionenDatei)));
    seite.querySelectorAll('[data-grenze]').forEach(b => b.addEventListener('click', () => zeigeGrenze(b.dataset.grenze)));
    seite.querySelectorAll('[data-zurueck]').forEach(b => b.addEventListener('click', () => { zustand.auswahl = null; leeren(); uebersicht(); schreibeAdresse(); }));
    seite.querySelectorAll('a[data-editor]').forEach(a => a.addEventListener('click', ev => { ev.preventDefault(); oeffneEditor(a.getAttribute('href')); }));
  }

  // ------------------------------------------------------------ 8. Auswahl und Sprungadressen
  let ausAdresse = false;
  function setzeAuswahl(a) { zustand.auswahl = a; schreibeAdresse(); }

  async function zeigeKnoten(id) {
    if (id === SAMMEL || inSammel.has(id)) {
      setzeAuswahl({ art: 'knoten', id });
      zustand.ebene = 'modul';
      if (veraltet()) await zeichne();
      hebeKnotenHervor(id);
      if (id === SAMMEL) sammelDetails(); else knotenDetails(id);
      return;
    }
    const k = knoten.get(id);
    if (!k) return;
    const ebene = ebeneVon(k);
    let neu = ebene !== zustand.ebene;
    if (k.art === 'datei') {
      if (k.rolle === 'test' && !zustand.mitTests) { zustand.mitTests = true; neu = true; }
      if (gross && !zustand.offen.has(behaelter(k))) { zustand.offen.add(behaelter(k)); neu = true; }
    }
    if (k.art === 'paket' && !k.fremd && !sichtbaresPaket(k)) { zustand.mitTests = true; neu = true; }
    if (k.art === 'modul' || k.art === 'ordner') zustand.zuletztModul = k.id;
    else if (k.art === 'datei') { zustand.zuletztModul = behaelter(k); zustand.zuletztDatei = k.pfad; }
    else zustand.zuletztModul = k.modul || k.ordner;
    zustand.ebene = ebene;
    setzeAuswahl({ art: 'knoten', id });
    if (neu || veraltet() || !cy.getElementById(id).nonempty()) await zeichne();
    hebeKnotenHervor(id);
    knotenDetails(id);
  }

  async function zeigeBefund(id) {
    const b = befundNachId.get(id);
    if (!b) return;
    setzeAuswahl({ art: 'befund', id });
    if (b.regel === 'zyklus') {
      const beleg = b.beleg;
      let neu = zustand.ebene !== beleg.ebene;
      zustand.ebene = beleg.ebene;
      if (beleg.rolle === 'mit-tests' && !zustand.mitTests) { zustand.mitTests = true; neu = true; }
      if (!zustand.zyklen) { zustand.zyklen = true; document.getElementById('u-zyklen').checked = true; neu = true; }
      const art = zustand.arten[beleg.ebene];
      const brauche = beleg.ebene === 'modul' ? [beleg.kantenart === 'gradle' ? 'gradle' : 'nutzt'] : beleg.ebene === 'datei' ? ['nutzt', 'jni'] : ['nutzt'];
      brauche.forEach(a => { if (!art[a]) { art[a] = true; neu = true; } });
      if (beleg.ebene === 'modul' && beleg.kantenart === 'gradle' && !zustand.plugins &&
        beleg.kanten.some(i => (kanteNachId.get(i) || {}).art === 'gradle-plugin')) { zustand.plugins = true; neu = true; }
      if (beleg.ebene === 'datei' && gross) {
        // Nur die Module des Zyklus ausklappen, damit die Ebene klein und schnell bleibt.
        const offen = new Set(beleg.knoten.map(m => behaelter(knoten.get(m))));
        if ([...offen].sort().join() !== [...zustand.offen].sort().join()) { zustand.offen = offen; neu = true; }
      }
      if (neu || veraltet()) await zeichne();
      hebeZyklusHervor(b);
    } else if (istMarkierung(b) || istDetekt(b)) {
      // Funktionen gibt es auf der Karte erst mit A09: hervorgehoben werden ihre Dateien.
      const dateien = [...new Set(b.knoten.map(dateiDerFunktion))].filter(id => knoten.has(id));
      if (istMarkierung(b) && !zustand.markierung) { zustand.markierung = true; document.getElementById('u-markierung').checked = true; }
      if (istDetekt(b) && !zustand.detekt) { zustand.detekt = true; document.getElementById('u-detekt').checked = true; }
      let neu = zustand.ebene !== 'datei';
      zustand.ebene = 'datei';
      if (dateien.some(id => knoten.get(id).rolle === 'test') && !zustand.mitTests) { zustand.mitTests = true; neu = true; }
      if (gross) dateien.forEach(id => { const g = behaelter(knoten.get(id)); if (!zustand.offen.has(g)) { zustand.offen.add(g); neu = true; } });
      if (neu || veraltet()) await zeichne();
      const sichtbar = [...new Set(dateien.map(sichtbarerKnoten).filter(Boolean))];
      if (sichtbar.length) fokus(sichtbar, { titel: befundTitel(b), ohneFluss: true });
      else leeren();
    } else {
      const ziel = b.knoten[0];
      const k = knoten.get(ziel);
      if (k && k.art === 'datei') {
        if (k.rolle === 'test') zustand.mitTests = true;
        if (gross) zustand.offen.add(behaelter(k));
        zustand.ebene = 'datei';
        if (veraltet() || !cy.getElementById(ziel).nonempty()) await zeichne();
        hebeKnotenHervor(ziel);
      } else if (veraltet()) await zeichne();
    }
    befundDetails(b);
  }

  // Kante zeigen: gemessene Kanten-Id (wechselt Ebene und klappt aus) oder Id einer Kante der Karte.
  async function zeigeKante(id, ebeneHinweis) {
    const k = kanteNachId.get(id);
    if (k) {
      const a = knoten.get(k.von), b = knoten.get(k.nach);
      if (!a || !b) return;
      const ebene = ebeneVon(a);
      let neu = ebene !== zustand.ebene;
      zustand.ebene = ebene;
      if (k.rolle === 'test' && !zustand.mitTests) { zustand.mitTests = true; neu = true; }
      const art = zustand.arten[ebene];
      const brauche = k.art.startsWith('gradle-') ? 'gradle' : k.art;
      if (art[brauche] === false) { art[brauche] = true; neu = true; }
      if (k.art === 'gradle-plugin' && !zustand.plugins) { zustand.plugins = true; neu = true; }
      if (ebene === 'datei' && gross) [a, b].forEach(d => { if (!zustand.offen.has(behaelter(d))) { zustand.offen.add(behaelter(d)); neu = true; } });
      if (neu || veraltet()) await zeichne();
    } else {
      if (ebeneHinweis && ARTEN_JE_EBENE[ebeneHinweis]) zustand.ebene = ebeneHinweis;
      if (veraltet()) await zeichne();
    }
    let e = cy.getElementById(id);
    if (e.empty() || !e.isEdge()) e = cy.edges().filter(x => x.data('kanten').includes(id));
    if (e.empty()) { uebersicht(); return; }
    e = e[0];
    setzeAuswahl({ art: 'kante', id: e.id(), ebene: zustand.ebene });
    hebeKanteHervor(e);
    kanteDetails(e);
  }

  function schreibeAdresse() {
    const a = zustand.auswahl;
    let hash;
    if (!a) hash = 'ebene=' + zustand.ebene;
    else if (a.art === 'kante') hash = 'ebene=' + a.ebene + '&kante=' + encodeURIComponent(a.id);
    else if (a.art === 'pfad') hash = 'ebene=' + a.ebene + '&von=' + encodeURIComponent(a.von) + '&nach=' + encodeURIComponent(a.nach);
    else if (a.art === 'fdatei') hash = 'datei-funktionen=' + encodeURIComponent(a.id);
    else if (a.art === 'funktion') {
      hash = 'funktion=' + encodeURIComponent(a.id);
      const w = zustand.weg;
      if (w && w.art === 'weg') hash = 'funktion=' + encodeURIComponent(w.start) + '&weg=' + w.richtung + '&tiefe=' + w.tiefe + (w.start !== a.id ? '&gewaehlt=' + encodeURIComponent(a.id) : '');
      else if (zustand.fDatei && fn(a.id) && fn(a.id).pfad !== zustand.fDatei) hash += '&datei-funktionen=' + encodeURIComponent(zustand.fDatei);
    } else hash = a.art + '=' + encodeURIComponent(a.id);
    if (location.hash === '#' + hash) return;
    try {
      // Jede neue Auswahl wird ein Eintrag im Verlauf, damit „Zurück“ zur vorherigen führt.
      if (ausAdresse || !location.hash) history.replaceState(null, '', '#' + hash);
      else history.pushState(null, '', '#' + hash);
    } catch (e) { /* ohne History */ }
  }

  async function leseAdresse() {
    ausAdresse = true;
    try {
      const p = new URLSearchParams(location.hash.replace(/^#/, ''));
      const ebene = p.get('ebene');
      if (ebene && ARTEN_JE_EBENE[ebene] && ebene !== 'funktion') zustand.ebene = ebene;
      // Adressen ohne Funktion verlassen den Wegmodus.
      if (!p.get('funktion')) zustand.weg = null;
      if (p.get('befund') && befundNachId.has(p.get('befund'))) { await zeigeBefund(p.get('befund')); return; }
      if (p.get('grenze') && befundNachId.has(p.get('grenze'))) { await zeigeGrenze(p.get('grenze')); return; }
      if (p.get('funktion') && fn(p.get('funktion'))) {
        const id = p.get('funktion'), weg = p.get('weg');
        if (weg === 'vor' || weg === 'rueck') {
          const tiefe = Math.min(5, Math.max(1, parseInt(p.get('tiefe'), 10) || 3));
          await zeigeWeg(id, weg, tiefe);
          const gewaehlt = p.get('gewaehlt');
          if (gewaehlt && cy.getElementById(gewaehlt).nonempty()) { setzeAuswahl({ art: 'funktion', id: gewaehlt }); hebeFunktionHervor(gewaehlt); funktionsDetails(gewaehlt); }
          return;
        }
        zustand.weg = null;
        const datei = p.get('datei-funktionen');
        if (datei && hatFunktionen(datei)) { if (datei !== zustand.fDatei) zustand.fAuf = new Set(); zustand.fDatei = datei; }
        else if (fn(id).pfad !== zustand.fDatei) { zustand.fAuf = new Set(); zustand.fDatei = fn(id).pfad; }
        await zeigeFunktion(id);
        return;
      }
      if (p.get('datei-funktionen')) { await zeigeFunktionsDatei(p.get('datei-funktionen')); return; }
      if (ebene === 'funktion' && p.get('von') && p.get('nach') && fn(p.get('von')) && fn(p.get('nach'))) { await zeigeFunktionsPfad(p.get('von'), p.get('nach')); return; }
      if (ebene === 'funktion') { await oeffneFunktionsebene(); return; }
      if (p.get('knoten') && (knoten.has(p.get('knoten')) || p.get('knoten') === SAMMEL)) { await zeigeKnoten(p.get('knoten')); return; }
      if (p.get('kante')) { await zeigeKante(p.get('kante'), ebene); return; }
      if (p.get('von') && p.get('nach')) { await zeigePfad(p.get('von'), p.get('nach')); uebersicht(); return; }
      zustand.auswahl = null;
      await zeichne();
      uebersicht();
    } finally {
      ausAdresse = false;
    }
  }

  // ------------------------------------------------------------ 9. Bedienung und Start
  function zeigeSchalter() {
    document.querySelectorAll('#ebenen button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.ebene === zustand.ebene)));
    document.querySelectorAll('#rollen button').forEach(b => b.setAttribute('aria-pressed', String((b.dataset.rolle === 'mit-tests') === zustand.mitTests)));
    ['gradle', 'nutzt', 'jni'].forEach(a => {
      const c = document.getElementById('k-' + a);
      const moeglich = ARTEN_JE_EBENE[zustand.ebene].includes(a);
      c.disabled = !moeglich;
      c.checked = moeglich && zustand.arten[zustand.ebene][a];
      c.closest('label').classList.toggle('aus', !moeglich);
    });
    ['lesen', 'unsicher'].forEach(a => {
      const c = document.getElementById('k-' + a);
      const moeglich = zustand.ebene === 'funktion';
      c.disabled = !moeglich;
      c.checked = a === 'lesen' ? lesenAn() : unsicherAn();
      c.closest('label').classList.toggle('aus', !moeglich);
    });
    const pl = document.getElementById('k-plugin');
    const plMoeglich = zustand.ebene === 'modul' && zustand.arten.modul.gradle;
    pl.disabled = !plMoeglich;
    pl.checked = plMoeglich && zustand.plugins;
    pl.closest('label').classList.toggle('aus', !plMoeglich);
    fuellePfadListe();
  }

  async function wendeAuswahlAn() {
    const a = zustand.auswahl;
    if (!a) return;
    if (a.art === 'befund') await zeigeBefund(a.id);
    else if (a.art === 'knoten') { if (sichtbarerKnoten(a.id)) hebeKnotenHervor(a.id); }
    else if (a.art === 'kante') { const e = cy.getElementById(a.id); if (e.nonempty()) hebeKanteHervor(e); }
    else if (a.art === 'pfad' && a.ebene === 'funktion') await zeigeFunktionsPfad(a.von, a.nach);
    else if (a.art === 'pfad') await zeigePfad(a.von, a.nach);
    else if (a.art === 'funktion') { if (cy.getElementById(a.id).nonempty() || zustand.ebene === 'funktion') { hebeFunktionHervor(a.id); funktionsDetails(a.id); } }
    else if (a.art === 'fdatei') dateiFunktionenSeite(a.id);
    else if (a.art === 'grenze') await zeigeGrenze(a.id);
  }

  async function neuZeichnen() {
    await zeichne();
    await wendeAuswahlAn();
  }

  // Ebenenwahl „Funktionen“: zuletzt gewählte Datei, sonst um eine Datei bitten.
  async function oeffneFunktionsebene() {
    const fd = fdaten();
    const kandidat = [zustand.zuletztDatei, zustand.fDatei].find(p => p && fd.nachDatei.has(p));
    if (kandidat) { await zeigeFunktionsDatei(kandidat); return; }
    zustand.ebene = 'funktion';
    zustand.fDatei = null;
    zustand.weg = null;
    zustand.auswahl = null;
    schreibeAdresse();
    fluss.stopp();
    leeren();
    cy.elements().remove();
    gezeichnet = layoutSchluessel();
    zeigeSchalter();
    zeigeWegInfo();
    document.documentElement.dataset.zustand = 'bereit';
    bitteUmDatei();
  }
  document.querySelectorAll('#ebenen button').forEach(b => b.addEventListener('click', async () => {
    if (b.dataset.ebene === 'funktion') { await oeffneFunktionsebene(); return; }
    zustand.weg = null;
    zustand.ebene = b.dataset.ebene;
    zustand.auswahl = null;
    schreibeAdresse();
    await zeichne();
    uebersicht();
  }));
  document.querySelectorAll('#rollen button').forEach(b => b.addEventListener('click', () => {
    zustand.mitTests = b.dataset.rolle === 'mit-tests';
    neuZeichnen();
  }));
  ['gradle', 'nutzt', 'jni'].forEach(a => document.getElementById('k-' + a).addEventListener('change', e => {
    zustand.arten[zustand.ebene][a] = e.target.checked;
    neuZeichnen();
  }));
  document.getElementById('k-plugin').addEventListener('change', e => { zustand.plugins = e.target.checked; neuZeichnen(); });
  // Im Wegmodus ab markierter Funktion bleibt der gemerkte Stand unberührt (siehe zeigeWeg).
  document.getElementById('k-lesen').addEventListener('change', e => {
    if (zustand.weg) zustand.wegLesen = e.target.checked;
    if (!zustand.weg || !wegAbMarkiert()) zustand.fLesen = e.target.checked;
    neuZeichnen();
  });
  document.getElementById('k-unsicher').addEventListener('change', e => { if (zustand.weg) zustand.wegUnsicher = e.target.checked; else zustand.fUnsicher = e.target.checked; neuZeichnen(); });
  document.getElementById('u-zyklen').addEventListener('change', e => { zustand.zyklen = e.target.checked; cy.style(stil()); });
  ['markierung', 'detekt'].forEach(schalter => document.getElementById('u-' + schalter).addEventListener('change', e => {
    zustand[schalter] = e.target.checked;
    const a = zustand.auswahl;
    if (zustand.ebene === 'funktion') {
      // Ersatzkanten der Markierung gehören zum Layout; sonst genügen die Klassen.
      if (schalter === 'markierung' && veraltet()) { neuZeichnen(); return; }
      fKlassen();
      if (a && a.art === 'funktion') funktionsDetails(a.id);
      return;
    }
    if (a && a.art === 'knoten') knotenDetails(a.id);
    else if (!a || a.art !== 'befund') uebersicht();
  }));
  document.getElementById('einpassen').addEventListener('click', () => passen(cy.elements(), 30));
  document.getElementById('zuruecksetzen').addEventListener('click', async () => {
    loeschePositionen(positionsEbene());
    await neuZeichnen();
  });

  // Symbole oben rechts an einem Kasten: Schloss, bei Dateien zusätzlich Editor und Code.
  function symbolGetroffen(n, pos) {
    const bb = n.boundingBox({ includeLabels: false, includeOverlays: false });
    if (pos.y < bb.y1 - 2 || pos.y > bb.y1 + 21 || pos.x > bb.x2 + 2) return null;
    const ab = bb.x2 - pos.x;
    if (ab <= 21) return 'schloss';
    if (n.data('typ') !== 'datei') return null;
    if (ab <= 39) return 'editor';
    if (ab <= 57) return 'code';
    return null;
  }

  // Symbole haben Vorrang vor Kanten, die über einen Kasten laufen.
  function symbolTippen(n, pos) {
    const sym = symbolGetroffen(n, pos);
    if (sym === 'schloss') schalteSperre(n);
    else if (sym === 'editor') { const d = knoten.get(n.id()); if (d) oeffneEditor(editorLink(d.pfad, 1)); }
    else if (sym === 'code') zeigeHinweis('Code-Ansicht kommt mit daidalos serve.');
    return !!sym;
  }
  cy.on('tap', 'node', e => {
    const n = e.target;
    if (symbolTippen(n, e.position)) return;
    if (zustand.ebene === 'funktion') { funktionTippen(n); return; }
    const ref = n.data('ref');
    if (!ref) return;
    zustand.zuletztModul = istGruppe(ref) ? ref : zustand.zuletztModul;
    setzeAuswahl({ art: 'knoten', id: ref });
    if (cy.getElementById(ref).nonempty()) hebeKnotenHervor(ref);
    else fokus([n.id()], { titel: name(ref) });
    knotenDetails(ref);
  });
  cy.on('tap', 'edge', e => {
    const k = e.target;
    const p = e.position;
    const darunter = cy.nodes().filter(n => { const bb = n.boundingBox({ includeLabels: false }); return p.x >= bb.x1 - 2 && p.x <= bb.x2 + 2 && p.y >= bb.y1 - 2 && p.y <= bb.y1 + 22; });
    for (const n of darunter.toArray().reverse()) if (symbolTippen(n, p)) return;
    if (zustand.ebene === 'funktion') {
      // Kanten der Funktionsebene haben keine eigene Sprungadresse.
      zustand.auswahl = { art: 'fkante', id: k.id() };
      hebeKanteHervor(k);
      fKanteDetails(k);
      return;
    }
    setzeAuswahl({ art: 'kante', id: k.id(), ebene: zustand.ebene });
    hebeKanteHervor(k);
    kanteDetails(k);
  });
  cy.on('dbltap', 'node', async e => {
    const n = e.target, ref = n.data('ref'), typ = n.data('typ');
    if (symbolGetroffen(n, e.position)) return;
    if (zustand.ebene === 'datei' && typ === 'datei') {
      const d = knoten.get(ref);
      if (d && hatFunktionen(d.pfad)) await zeigeFunktionsDatei(d.pfad);
      else zeigeHinweis('Diese Datei hat keine Funktionen auf der Funktionsebene.');
      return;
    }
    if (zustand.ebene === 'funktion') {
      // Doppelklick auf eine fremde Funktion oder Datei öffnet deren Datei.
      const pfad = n.data('pfad');
      if (!pfad || (pfad === zustand.fDatei && !zustand.weg)) return;
      zustand.weg = null;
      if (typ === 'funktion') { zustand.fAuf = new Set(); zustand.fDatei = pfad; await zeigeFunktion(ref); }
      else await zeigeFunktionsDatei(pfad);
      return;
    }
    if (zustand.ebene === 'modul' && istGruppe(ref)) {
      zustand.zuletztModul = ref;
      zustand.ebene = 'paket';
      setzeAuswahl({ art: 'knoten', id: ref });
      await zeichne();
      hebeKnotenHervor(ref);
      knotenDetails(ref);
    } else if (zustand.ebene === 'paket' && typ === 'paket') {
      const p = knoten.get(ref);
      zustand.zuletztModul = p.modul || p.ordner;
      if (gross) zustand.offen.add(zustand.zuletztModul);
      zustand.ebene = 'datei';
      setzeAuswahl({ art: 'knoten', id: ref });
      await zeichne();
      hebeKnotenHervor(ref);
      knotenDetails(ref);
    } else if (zustand.ebene === 'datei' && gross && (typ === 'gruppe' || typ === 'zu')) {
      if (zustand.offen.has(ref)) zustand.offen.delete(ref); else zustand.offen.add(ref);
      zustand.zuletztModul = ref;
      await zeichne();
      hebeKnotenHervor(ref);
    }
  });
  function aufheben() {
    if (zustand.ebene === 'funktion' && zustand.fDatei) {
      leeren();
      zeigeWegInfo();
      if (zustand.weg && zustand.weg.art === 'weg') { setzeAuswahl({ art: 'funktion', id: zustand.weg.start }); funktionsDetails(zustand.weg.start); return; }
      if (!zustand.weg) { setzeAuswahl({ art: 'fdatei', id: zustand.fDatei }); dateiFunktionenSeite(zustand.fDatei); return; }
    }
    zustand.auswahl = null; leeren(); uebersicht(); schreibeAdresse();
  }
  // Klick auf der Funktionsebene: Funktion wählen, zusammengefasste Datei aufklappen, Rahmen zeigen.
  async function funktionTippen(n) {
    const typ = n.data('typ'), ref = n.data('ref');
    if (typ === 'funktion') {
      setzeAuswahl({ art: 'funktion', id: ref });
      hebeFunktionHervor(ref);
      funktionsDetails(ref);
    } else if (typ === 'fzu') {
      zustand.fAuf.add(n.data('pfad'));
      await neuZeichnen();
    } else if (ref) {
      fokus([n.id()], { titel: dateiName(n.data('pfad') || ref) });
      zeigeWegInfo();
      if (typ === 'fdatei' && !zustand.weg) { setzeAuswahl({ art: 'fdatei', id: zustand.fDatei }); dateiFunktionenSeite(zustand.fDatei); }
      else knotenDetails(ref);
    }
  }
  cy.on('tap', e => { if (e.target === cy) aufheben(); });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !(e.target instanceof HTMLInputElement)) aufheben();
  });
  window.addEventListener('popstate', leseAdresse);
  window.addEventListener('resize', () => cy.resize());

  // Hinweise (z. B. ausgegraute Symbole)
  const toast = document.getElementById('toast');
  let toastZeit = 0;
  function zeigeHinweis(text) {
    toast.textContent = text;
    toast.classList.add('an');
    clearTimeout(toastZeit);
    toastZeit = setTimeout(() => toast.classList.remove('an'), 3200);
  }

  // Darstellung: Dunkel ist Standard, die Wahl merkt sich der Browser, wenn er darf.
  function setzeThema(t) {
    if (t === 'system') document.documentElement.removeAttribute('data-theme'); else document.documentElement.setAttribute('data-theme', t);
    document.querySelectorAll('.thema button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.thema === t)));
    try { localStorage.setItem('daidalos-thema', t); } catch (e) { /* ohne Speicher */ }
    cy.style(stil());
  }

  // ------------------------------------------------------------ 10. Sperren und Positionen
  // Standardmäßig ist alles gesperrt. `eigen` hält, was der Nutzer an einem Element umgestellt hat;
  // ohne eigenen Zustand gilt der des nächsten Behälters, sonst der globale.
  const sperre = { alle: false, eigen: new Map() };
  function istOffenGesperrt(n) {
    if (sperre.eigen.has(n.id())) return sperre.eigen.get(n.id());
    const v = n.ancestors().filter(a => sperre.eigen.has(a.id()));
    return v.nonempty() ? sperre.eigen.get(v[0].id()) : sperre.alle;
  }
  function sperren() {
    let offen = 0;
    cy.batch(() => cy.nodes().forEach(n => {
      const o = istOffenGesperrt(n);
      if (o) { n.unlock(); offen++; } else n.lock();
      n.toggleClass('offen', o);
    }));
    const b = document.getElementById('schloss');
    const alle = cy.nodes().length;
    const text = offen && offen === alle ? 'alle entsperrt' : offen ? offen + ' entsperrt' : 'alle gesperrt';
    b.innerHTML = (offen ? SVG_AUF : SVG_ZU) + '<span>' + text + '</span>';
    b.setAttribute('aria-pressed', String(!offen));
    b.title = offen ? 'Alle Elemente sperren' : 'Alle Elemente zum Verschieben entsperren';
  }
  function schalteSperre(n) {
    sperre.eigen.set(n.id(), !istOffenGesperrt(n));
    sperren();
  }
  document.getElementById('schloss').addEventListener('click', () => {
    const offen = cy.nodes().some(n => istOffenGesperrt(n));
    sperre.alle = !offen;
    sperre.eigen.clear();
    sperren();
  });

  // Gemerkte Positionen je Projekt, Ebene und Knoten-Id (nur Blätter; Behälter folgen ihrem Inhalt).
  // Das Projekt erkennt der Schlüssel an ziel.name, dem eingebetteten Weg zur Repo-Wurzel und dem
  // Ablageort der Karte, damit zwei gleichnamige Projekte sich nicht in die Quere kommen.
  function ablageort() {
    if (location.protocol !== 'file:') return location.origin + location.pathname;
    return (location.host ? '//' + location.host : '') + decodeURIComponent(location.pathname);
  }
  const speicherName = ebene => ['daidalos-positionen', M.ziel.name, E.wurzel === null || E.wurzel === undefined ? '' : E.wurzel, ablageort(), ebene].join('|');
  const alterSpeicherName = ebene => 'daidalos-positionen|' + M.ziel.name + '|' + ebene;  // bis A05
  // Einträge unter dem alten Schlüssel einmal übernehmen; der alte Eintrag fällt dabei weg.
  function uebernimmAltePositionen() {
    try {
      Object.keys(ARTEN_JE_EBENE).forEach(ebene => {
        const alt = localStorage.getItem(alterSpeicherName(ebene));
        if (alt === null) return;
        if (localStorage.getItem(speicherName(ebene)) === null) localStorage.setItem(speicherName(ebene), alt);
        localStorage.removeItem(alterSpeicherName(ebene));
      });
    } catch (e) { /* ohne Speicher */ }
  }
  uebernimmAltePositionen();
  function lesePositionen(ebene) {
    try { return JSON.parse(localStorage.getItem(speicherName(ebene)) || '{}') || {}; } catch (e) { return {}; }
  }
  function schreibePositionen(ebene, pos) {
    try { localStorage.setItem(speicherName(ebene), JSON.stringify(pos)); } catch (e) { /* ohne Speicher */ }
  }
  function loeschePositionen(ebene) {
    try { localStorage.removeItem(speicherName(ebene)); } catch (e) { /* ohne Speicher */ }
  }
  const ROUTEN_WEG = ROUTEN_STIL.join(' ');
  // Kanten an verschobenen Knoten verlieren ELKs Führung und fallen auf Bézier zurück.
  function ohneRoute(blaetter) {
    blaetter.connectedEdges().forEach(e => { if (e.style('curve-style') !== 'bezier' && zustand.kantenfuehrung === 'elk') e.removeStyle(ROUTEN_WEG); });
  }
  // Funktionsebene: Schlüssel je Datei (Wirkungswege je Start, Richtung und Tiefe).
  function positionsEbene() {
    if (zustand.ebene !== 'funktion') return zustand.ebene;
    const w = zustand.weg;
    if (!w) return 'funktion:' + zustand.fDatei;
    return w.art === 'weg' ? 'funktion-weg:' + w.start + ':' + w.richtung + ':' + w.tiefe : 'funktion-pfad:' + w.von + ':' + w.nach;
  }
  function wendePositionenAn() {
    const pos = lesePositionen(positionsEbene());
    let verschoben = cy.collection();
    cy.batch(() => cy.nodes().forEach(n => {
      const p = pos[n.id()];
      if (!n.isChildless() || !p) return;
      n.position({ x: p[0], y: p[1] });
      verschoben = verschoben.union(n);
    }));
    ohneRoute(verschoben);
  }
  // Beim Ziehen eines Behälters bleiben gesperrte Elemente darin an ihrem Platz.
  let vorZiehen = null;
  cy.on('grab', 'node', e => {
    const n = e.target;
    if (n.locked()) { vorZiehen = null; return; }
    const fest = n.descendants().filter(x => x.isChildless() && !istOffenGesperrt(x));
    vorZiehen = new Map(fest.map(x => [x.id(), Object.assign({}, x.position())]));
    ohneRoute(blattVon(n));
  });
  cy.on('drag', 'node', () => {
    if (!vorZiehen || !vorZiehen.size) return;
    cy.batch(() => vorZiehen.forEach((p, id) => cy.getElementById(id).position(p)));
  });
  cy.on('free', 'node', e => {
    const n = e.target;
    if (n.locked()) return;
    const pos = lesePositionen(positionsEbene());
    blattVon(n).forEach(x => { if (!vorZiehen || !vorZiehen.has(x.id())) { const p = x.position(); pos[x.id()] = [Math.round(p.x * 10) / 10, Math.round(p.y * 10) / 10]; } });
    schreibePositionen(positionsEbene(), pos);
    vorZiehen = null;
  });

  // ------------------------------------------------------------ 11. Pfad-Suche
  // Dieselbe Logik wie `daidalos pfad`: Kanten `nutzt` (Modulebene zusätzlich Gradle), Rolle nach
  // dem Schalter, Breitensuche mit Nachbarn nach Id sortiert.
  const ART_EBENE = { modul: 'modul', ordner: 'modul', paket: 'paket', datei: 'datei' };
  function sucheWeg(von, nach, ebene, mitTests) {
    const nachbarn = new Map();
    M.kanten.forEach(k => {
      if (k.art !== 'nutzt' && !(ebene === 'modul' && k.art.startsWith('gradle-'))) return;
      if (!mitTests && k.rolle !== 'produktiv') return;
      const a = knoten.get(k.von), b = knoten.get(k.nach);
      if (!a || !b || ART_EBENE[a.art] !== ebene || ART_EBENE[b.art] !== ebene) return;
      if (!nachbarn.has(k.von)) nachbarn.set(k.von, new Map());
      const z = nachbarn.get(k.von);
      if (!z.has(k.nach)) z.set(k.nach, []);
      z.get(k.nach).push(k);
    });
    const vorgaenger = new Map([[von, null]]);
    const offen = [von];
    while (offen.length) {
      const aktuell = offen.shift();
      if (aktuell === nach) break;
      [...(nachbarn.get(aktuell) || new Map()).keys()].sort((a, b) => a < b ? -1 : a > b ? 1 : 0).forEach(z => {
        if (!vorgaenger.has(z)) { vorgaenger.set(z, aktuell); offen.push(z); }
      });
    }
    if (!vorgaenger.has(nach)) return null;
    const kette = [nach];
    while (vorgaenger.get(kette[kette.length - 1]) !== null) kette.push(vorgaenger.get(kette[kette.length - 1]));
    kette.reverse();
    return { knoten: kette, schritte: kette.slice(1).map((b, i) => nachbarn.get(kette[i]).get(b).slice().sort((x, y) => x.art < y.art ? -1 : x.art > y.art ? 1 : x.id < y.id ? -1 : 1)) };
  }

  // Vorschläge: Knoten der aktuellen Ebene, Text ist der Pfad (Dateien) bzw. Name.
  let pfadListe = new Map(), pfadListeEbene = null;
  function pfadText(k) {
    if (k.art === 'datei') return k.pfad;
    if (k.art === 'paket') return k.name + ' · ' + name(k.modul || k.ordner);
    return name(k.id);
  }
  function fuellePfadListe() {
    if (pfadListeEbene === zustand.ebene) return;
    pfadListeEbene = zustand.ebene;
    pfadListe = new Map();
    if (zustand.ebene === 'funktion') {
      fdaten().fn.forEach(f => { if (!f.implizit) pfadListe.set(f.kurz + ' · ' + dateiName(f.pfad), f.id); });
      document.getElementById('pfad-liste').innerHTML = [...pfadListe.keys()].sort().map(t => `<option value="${esc(t)}"></option>`).join('');
      return;
    }
    M.knoten.forEach(k => { if (ART_EBENE[k.art] === zustand.ebene && !k.fremd && (k.art !== 'datei' || aufKarte.has(k.id))) pfadListe.set(pfadText(k), k.id); });
    const dl = document.getElementById('pfad-liste');
    dl.innerHTML = [...pfadListe.keys()].sort().map(t => `<option value="${esc(t)}"></option>`).join('');
  }
  function findePfadKnoten(text) {
    const t = text.trim();
    if (!t) return { fehler: 'leer' };
    if (pfadListe.has(t)) return { id: pfadListe.get(t) };
    if (knoten.has(t) && ART_EBENE[knoten.get(t).art] === zustand.ebene) return { id: t };
    const klein = t.toLowerCase();
    const treffer = zustand.ebene === 'funktion' ? [] : [...pfadListe.entries()].filter(([s]) => s.toLowerCase().includes(klein));
    if (treffer.length === 1) return { id: treffer[0][1] };
    if (treffer.length) return { fehler: '„' + t + '“ passt auf ' + treffer.length + ' Knoten' };
    // Funktionen: Id oder Suchbegriff wie bei `daidalos pfad` (Teil hinter #, auch ohne /n).
    const fd = fdaten();
    if (fd.nachId.has(t)) return { id: t };
    const passend = fd.fn.filter(f => f.kurz === t || f.kurz.startsWith(t + '/'));
    if (passend.length === 1) return { id: passend[0].id };
    return { fehler: passend.length ? '„' + t + '“ passt auf ' + passend.length + ' Funktionen' : 'kein Knoten und keine Funktion passt zu „' + t + '“' };
  }

  async function zeigePfad(von, nach) {
    const a = knoten.get(von), b = knoten.get(nach);
    if (!a || !b) return null;
    const ebene = ART_EBENE[a.art];
    if (ebene !== ART_EBENE[b.art]) return null;
    const weg = sucheWeg(von, nach, ebene, zustand.mitTests);
    // Der Weg muss auf der Karte zu sehen sein: Ebene, Kantenarten, ausgeklappte Module.
    let neu = zustand.ebene !== ebene;
    zustand.ebene = ebene;
    if (weg) {
      const arten = zustand.arten[ebene];
      weg.schritte.forEach(ks => {
        const brauche = ks.some(k => k.art === 'nutzt') ? 'nutzt' : 'gradle';
        if (!arten[brauche]) { arten[brauche] = true; neu = true; }
        if (brauche === 'gradle' && ks.every(k => k.art === 'gradle-plugin') && !zustand.plugins) { zustand.plugins = true; neu = true; }
      });
      if (ebene === 'datei' && gross) weg.knoten.forEach(id => { const g = behaelter(knoten.get(id)); if (!zustand.offen.has(g)) { zustand.offen.add(g); neu = true; } });
    }
    setzeAuswahl({ art: 'pfad', von, nach, ebene });
    if (neu || veraltet()) await zeichne();
    leeren();
    if (!weg) {
      pfadinfo.textContent = name(von) + ' hängt nicht an ' + name(nach) + ' (über ' + (ebene === 'modul' ? 'nutzt- und Gradle-Kanten' : 'nutzt-Kanten') + ', ' + (zustand.mitTests ? 'mit Tests' : 'nur produktiv') + ').';
      pfadinfo.hidden = false;
      return null;
    }
    const nks = cy.collection(weg.knoten.map(id => cy.getElementById(id)).filter(n => n.nonempty()));
    let eks = cy.collection();
    weg.knoten.slice(1).forEach((z, i) => {
      const q = weg.knoten[i];
      const ids = new Set(weg.schritte[i].map(k => k.id));
      let e = cy.edges().filter(x => x.source().id() === q && x.target().id() === z && x.data('kanten').some(id => ids.has(id)));
      if (e.empty()) e = cy.edges().filter(x => x.source().id() === q && x.target().id() === z);
      eks = eks.union(e);
    });
    abblenden(nks.union(eks));
    nks.addClass('hl');
    eks.addClass('hl');
    nks.first().addClass('gewaehlt');
    fluss.start(eks);
    pfadinfo.textContent = weg.knoten.map(name).join(' → ');
    pfadinfo.hidden = false;
    passen(nks.union(eks), 70);
    return weg.knoten;
  }

  document.getElementById('pfad-los').addEventListener('click', async () => {
    const v = findePfadKnoten(document.getElementById('pfad-von').value);
    const n = findePfadKnoten(document.getElementById('pfad-nach').value);
    if (v.fehler || n.fehler) {
      leeren();
      pfadinfo.textContent = 'Warum hängt …: ' + [v.fehler && 'Von: ' + v.fehler, n.fehler && 'Nach: ' + n.fehler].filter(Boolean).join(' · ');
      pfadinfo.hidden = false;
      return;
    }
    const vf = v.id.startsWith('funktion:'), nf = n.id.startsWith('funktion:');
    if (vf || nf) {
      if (vf && nf) { await zeigeFunktionsPfad(v.id, n.id); return; }
      leeren();
      pfadinfo.textContent = 'Warum hängt …: Von und Nach müssen beide Funktionen sein oder beide Knoten derselben Ebene.';
      pfadinfo.hidden = false;
      return;
    }
    zustand.weg = null;
    await zeigePfad(v.id, n.id);
    uebersicht();
  });
  ['pfad-von', 'pfad-nach'].forEach(id => document.getElementById(id).addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('pfad-los').click(); }));

  // ------------------------------------------------------------ 12. Editor-Links
  // Die Karte liegt in <repo>/docs/daidalos/; die Repo-Wurzel ergibt sich aus der eigenen Adresse
  // und dem eingebetteten relativen Weg. In karte.html steht so nie ein absoluter Pfad.
  function editorBasis() {
    if (location.protocol !== 'file:' || E.wurzel === null || E.wurzel === undefined) return null;
    const teile = decodeURIComponent(location.pathname).split('/');
    teile.pop();  // karte.html
    E.wurzel.split('/').forEach(s => { if (s === '..') teile.pop(); else if (s && s !== '.') teile.push(s); });
    let basis = teile.filter((s, i) => s || i === 0).join('/');
    if (location.host) basis = '//' + location.host + basis;  // Netzlaufwerk (UNC)
    return basis;
  }
  const editorGrund = () => location.protocol !== 'file:'
    ? 'Im Editor öffnen geht nur, wenn die Karte als Datei (file://) geöffnet ist.'
    : 'Die Karte liegt nicht im Zielrepo; ohne Repo-Wurzel kein Editor-Link.';
  function editorLink(relPfad, zeile) {
    const basis = editorBasis();
    if (basis === null) return null;
    const voll = (basis + '/' + relPfad).replace(/^\/+(?=[A-Za-z]:\/)/, '').replace(/^\/(?!\/)/, '');
    const kodiert = voll.split('/').map((s, i) => i === 0 && /^[A-Za-z]:$/.test(s) ? s : encodeURIComponent(s)).join('/');
    return E.editor_link.split('{pfad}').join(kodiert).split('{zeile}').join(String(zeile || 1));
  }
  function editorKnopf(relPfad, zeile, klein) {
    const link = editorLink(relPfad, zeile);
    const titel = link ? 'Im Editor öffnen: ' + relPfad + ':' + zeile : editorGrund();
    const inhalt = SVG_EDITOR + (klein ? '' : 'Editor');
    return link
      ? `<a class="${klein ? 'ed' : 'sym'}" data-editor href="${esc(link)}" title="${esc(titel)}" aria-label="${esc(titel)}">${inhalt}</a>`
      : `<button type="button" class="${klein ? 'ed' : 'sym'}" disabled title="${esc(titel)}" aria-label="${esc(titel)}">${inhalt}</button>`;
  }
  let letzterLink = null;
  function oeffneEditor(link) {
    if (!link) { zeigeHinweis(editorGrund()); return; }
    letzterLink = link;
    const a = document.createElement('a');
    a.href = link;
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
    zeigeHinweis('Öffne im Editor: ' + link);
  }

  // ------------------------------------------------------------ 13. Funktionsebene (seit A09)
  // Fokus-Ansicht: eine Datei mit ihren Klassen und Funktionen und den Nachbarn, die hierher
  // rufen oder von hier gerufen werden; dazu der Wirkungsweg vorwärts und rückwärts. Der Block
  // id="funktionen" wird erst beim ersten Öffnen gelesen, damit die Karte schnell startet.
  const GRENZE_KAESTEN = 150;
  const KLASSEN_ART = { klasse: 'Klasse', schnittstelle: 'Schnittstelle', objekt: 'Objekt', companion: 'Companion', enum: 'Enum', annotation: 'Annotation', 'enum-eintrag': 'Eintrag' };
  const HOCH = '⁰¹²³⁴⁵⁶⁷⁸⁹';
  const hoch = n => String(n).split('').map(c => HOCH[c] || c).join('');
  const ART_TEXT = { ruft: 'ruft', lesen: 'liest', schreiben: 'schreibt', ueberschreibt: 'überschreibt', actual: 'actual zu', jni: 'JNI', grenze: 'Grenzkante' };
  let FD = null;

  function fdaten() {
    if (FD) return FD;
    const beginn = performance.now();
    const roh = JSON.parse(document.getElementById('funktionen').textContent);
    FD = { da: !!roh, fn: [], nachId: new Map(), nachDatei: new Map(), kanten: [], raus: [], rein: [], klassen: new Map(), detekt: new Map() };
    if (roh) {
      const f = {};
      roh.felder.forEach((n, i) => { f[n] = i; });
      const mk = roh.merkmale;
      roh.funktionen.forEach((z, i) => {
        const pfad = roh.dateien[z[f.datei]];
        const kurz = z[f.kurz], beh = z[f.behaelter], m = z[f.merkmale];
        const o = {
          i, id: 'funktion:' + pfad + '#' + kurz, pfad, kurz, behaelter: beh,
          name: beh && kurz.startsWith(beh + '.') ? kurz.slice(beh.length + 1) : kurz,
          von: z[f.zeile_von], bis: z[f.zeile_bis],
          markiert: !!(m & mk.markiert), ausnahme: !!(m & mk.ausnahme), ohneKoerper: !!(m & mk.ohne_koerper),
          implizit: !!(m & mk.implizit), test: !!(m & mk.test), c: !!(m & mk.c),
          komplex: z[f.komplexitaet], zeilen: z[f.zeilen], fanIn: z[f.fan_in], fanInU: z[f.fan_in_unsicher],
          fanOut: z[f.fan_out], fanOutU: z[f.fan_out_unsicher], extern: z[f.externe_aufrufe], delegiert: z[f.delegiert_gelesen],
          sicht: z[f.sichtbarkeit], mods: z[f.modifikatoren], params: z[f.parameter], vorgabe: z[f.parameter_vorgabe],
          vararg: z[f.parameter_vararg], annot: z[f.annotationen], erw: z[f.erweiterung], markierung: z[f.markierung]
        };
        FD.fn.push(o);
        FD.nachId.set(o.id, o);
        if (!FD.nachDatei.has(pfad)) FD.nachDatei.set(pfad, []);
        FD.nachDatei.get(pfad).push(i);
        FD.raus.push([]); FD.rein.push([]);
      });
      roh.kanten.forEach(([v, n, a, s, g, zeile, h, gr], e) => {
        const k = { e, id: 'fe:' + e, v, n, art: roh.arten[a], sicher: !!s, gewicht: g, zeile, herkunft: h >= 0 ? roh.texte[h] : null, grund: gr >= 0 ? roh.texte[gr] : null };
        FD.kanten.push(k); FD.raus[v].push(k); FD.rein[n].push(k);
      });
      roh.dateien.forEach((p, i) => FD.klassen.set(p, new Map(roh.klassen[i].map(([name, art, zeile]) => [name, { art, zeile }]))));
    }
    M.befunde.forEach(b => {
      if (!istDetekt(b) || !b.knoten[0].startsWith('funktion:')) return;
      if (!FD.detekt.has(b.knoten[0])) FD.detekt.set(b.knoten[0], []);
      FD.detekt.get(b.knoten[0]).push(b);
    });
    zeiten.funktionenLesen = Math.round(performance.now() - beginn);
    return FD;
  }
  const fn = id => fdaten().nachId.get(id);
  const hatFunktionen = pfad => (fdaten().nachDatei.get(pfad) || []).length > 0;
  // Grenzkanten der Markierungs-Kette, die der Schalter zeigt: Paar "von|nach" → Befund.
  function grenzPaare() {
    const paare = new Map();
    if (!zustand.markierung) return paare;
    M.befunde.forEach(b => { if (istMarkierung(b)) paare.set(b.beleg.von + '|' + b.beleg.nach, b); });
    return paare;
  }

  // Schalter „unsicher“: Dateiansicht und Wegmodus haben eigene Stände.
  function unsicherAn() { return zustand.weg ? zustand.wegUnsicher : zustand.fUnsicher; }
  // Schalter „Lesezugriffe“: Ein Wirkungsweg ab einer markierten Funktion zeigt sie standardmäßig,
  // weil die Markierungs-Kette sie mitzählt (A09b); sonst gilt der gemerkte Stand.
  function lesenAn() { return zustand.weg ? zustand.wegLesen : zustand.fLesen; }
  function wegAbMarkiert() {
    const w = zustand.weg;
    return !!w && w.art === 'weg' && !!fn(w.start) && !!fn(w.start).markiert;
  }
  // Kanten der Funktionsebene nach den Schaltern „Lesezugriffe“, „unsicher“ und „mit Tests“.
  function fKanteSichtbar(k) {
    if ((k.art === 'lesen' || k.art === 'schreiben') && !lesenAn()) return false;
    if (!k.sicher && !unsicherAn()) return false;
    if (!zustand.mitTests && FD.fn[k.v].test) return false;
    return true;
  }

  function signaturKurz(f) { return f.name; }
  function symbolCode(f) {
    return (f.markiert ? 1 : 0) | (f.ausnahme ? 2 : 0) | (zustand.detekt && FD.detekt.has(f.id) ? 4 : 0);
  }
  function fKasten(f, parent, mitBehaelter) {
    const text = mitBehaelter ? f.kurz : signaturKurz(f);
    const label = text + (f.komplex !== null && f.komplex !== undefined ? ' ' + hoch(f.komplex) : '');
    const e = blatt(f.id, [label], 'funktion', { parent, ref: f.id, fi: f.i, sym: symbolCode(f), pfad: f.pfad });
    const cls = [];
    if (f.ohneKoerper || f.implizit) cls.push('ohneKoerper');
    if (f.test) cls.push('test');
    e.classes = cls.join(' ');
    return e;
  }
  // Rahmen der umgebenden Klassen (von außen nach innen); liefert den Rahmen der Funktion.
  function rahmenKette(pfad, behaelter, wurzel, els, gesehen) {
    if (!behaelter) return wurzel;
    const teile = behaelter.split('.');
    let eltern = wurzel;
    for (let i = 1; i <= teile.length; i++) {
      const kette = teile.slice(0, i).join('.');
      const id = 'fk:' + pfad + '#' + kette;
      if (!gesehen.has(id)) {
        gesehen.add(id);
        const k = (FD.klassen.get(pfad) || new Map()).get(kette);
        const art = k ? KLASSEN_ART[k.art] || k.art : 'Klasse';
        const teil = teile[i - 1];
        els.push({ group: 'nodes', data: { id, label: art === 'Companion' && teil === 'Companion' ? 'Companion' : art + ' ' + teil, typ: 'fklasse', parent: eltern, ref: 'datei:' + pfad, pfad } });
      }
      eltern = id;
    }
    return eltern;
  }
  const dateiName = pfad => pfad.split('/').pop();

  // Elemente der Funktionsansicht einer Datei (zustand.fDatei) oder des Wegmodus.
  function funktionsElemente() {
    const fd = fdaten();
    const kanten = sammler();
    const els = zustand.weg ? wegElemente(kanten) : dateiFunktionsElemente(kanten);
    kanten.werte().forEach(e => {
      const d = e.data;
      d.breite = d.art === 'lesen' || d.art === 'schreiben' ? 0.9 : breite(d.gewicht);
      d.label = d.gewicht >= 2 ? String(d.gewicht) : '';
      const cls = [e.classes || ''];
      if (d.unsicher) cls.push('unsicher');
      if (d.verdichtet) cls.push('verdichtet');
      if (d.art === 'lesen' || d.art === 'schreiben') cls.push('zugriff');
      if (d.art === 'ueberschreibt' || d.art === 'actual') cls.push('punkt');
      if (d.art === 'jni') cls.push('jni');
      e.classes = cls.join(' ').trim();
      els.push(e);
    });
    zustand.fKaesten = els.filter(e => e.group === 'nodes' && (e.data.typ === 'funktion' || e.data.typ === 'fzu')).length;
    void fd;
    return els;
  }

  function dateiFunktionsElemente(kanten) {
    const fd = FD;
    const pfad = zustand.fDatei;
    const els = [];
    const eigene = (fd.nachDatei.get(pfad) || []).map(i => fd.fn[i]);
    const eigen = new Set(eigene.map(f => f.i));
    const rahmen = 'ff:' + pfad;
    const gesehen = new Set();
    const eigeneEls = [];
    eigene.forEach(f => eigeneEls.push(fKasten(f, rahmenKette(pfad, f.behaelter, rahmen, eigeneEls, gesehen), false)));
    const liste = [];
    eigene.forEach(f => {
      fd.raus[f.i].forEach(k => { if (fKanteSichtbar(k)) liste.push(k); });
      fd.rein[f.i].forEach(k => { if (!eigen.has(k.v) && fKanteSichtbar(k)) liste.push(k); });
    });
    // Nachbarn je fremder Datei; Aufrufer (nur rufend) zuerst, damit sie links stehen.
    const nachbarn = new Map(), rufend = new Map();
    liste.forEach(k => [k.v, k.n].forEach(i => {
      if (eigen.has(i)) return;
      const p = fd.fn[i].pfad;
      if (!nachbarn.has(p)) { nachbarn.set(p, new Set()); rufend.set(p, true); }
      nachbarn.get(p).add(i);
      if (i === k.n) rufend.set(p, false);
    }));
    // Grenze: Nachbardateien mit den meisten Funktionen zusammenfassen, bis es passt.
    let kaesten = eigene.length;
    nachbarn.forEach(m => { kaesten += m.size; });
    const zu = new Set();
    const nachGroesse = [...nachbarn.entries()].sort((a, b) => b[1].size - a[1].size || (a[0] < b[0] ? -1 : 1));
    for (const [p, m] of nachGroesse) {
      if (kaesten <= GRENZE_KAESTEN) break;
      if (zustand.fAuf.has(p) || m.size < 2) continue;
      zu.add(p);
      kaesten -= m.size - 1;
    }
    zustand.fZu = zu;
    // Gleichnamige Dateien (etwa aus verschiedenen Modulen) mit ihrem ersten Pfadteil.
    const zahlName = new Map();
    [pfad, ...nachbarn.keys()].forEach(p => zahlName.set(dateiName(p), (zahlName.get(dateiName(p)) || 0) + 1));
    const titel = p => zahlName.get(dateiName(p)) > 1 ? p.split('/')[0] + ' · ' + dateiName(p) : dateiName(p);
    const ort = new Map(eigene.map(f => [f.i, f.id]));
    const nachbarEls = (nurRufend) => {
      const teil = [];
      [...nachbarn.keys()].sort().forEach(p => {
        if (rufend.get(p) !== nurRufend) return;
        const m = nachbarn.get(p);
        if (zu.has(p)) {
          teil.push(blatt('fz:' + p, [titel(p) + ' (+' + m.size + ')'], 'fzu', { ref: 'datei:' + p, pfad: p }));
          m.forEach(i => ort.set(i, 'fz:' + p));
          return;
        }
        teil.push({ group: 'nodes', data: { id: 'fn:' + p, label: titel(p), typ: 'fnachbar', ref: 'datei:' + p, pfad: p } });
        [...m].sort((a, b) => a - b).forEach(i => { const f = fd.fn[i]; teil.push(fKasten(f, 'fn:' + p, true)); ort.set(i, f.id); });
      });
      return teil;
    };
    els.push(...nachbarEls(true));
    els.push({ group: 'nodes', data: { id: rahmen, label: dateiName(pfad), typ: 'fdatei', ref: 'datei:' + pfad, pfad } });
    els.push(...eigeneEls);
    els.push(...nachbarEls(false));
    liste.forEach(k => {
      const q = ort.get(k.v), z = ort.get(k.n);
      kanten.add(q, z, k.art, k, q !== fd.fn[k.v].id || z !== fd.fn[k.n].id);
    });
    grenzErsatz(els, ort, liste);
    return els;
  }
  // Grenzkanten ohne eigene Kante in der Ansicht (über ueberschreibt erreicht): Ersatzkante.
  function grenzErsatz(els, ort, liste) {
    const da = new Set(liste.map(k => FD.fn[k.v].id + '|' + FD.fn[k.n].id));
    grenzPaare().forEach((b, paar) => {
      if (da.has(paar)) return;
      const v = fn(b.beleg.von), n = fn(b.beleg.nach);
      if (!v || !n || !ort.has(v.i) || !ort.has(n.i) || ort.get(v.i) === ort.get(n.i)) return;
      els.push({ group: 'edges', data: { id: 'fg:' + b.id, source: ort.get(v.i), target: ort.get(n.i), art: 'grenze', gewicht: 1, kanten: [], befund: b.id, unsicher: !!b.beleg.unsicher, verdichtet: false, breite: 1.6, label: '' }, classes: 'grenze' });
    });
  }

  // ---- Wirkungsweg: dieselben Regeln wie `daidalos aufrufe` (ohne Wiederholung, Schalter für
  // unsicher, Lesezugriffe und Tests), dazu wie in der Markierungs-Kette (A08) ueberschreibt/actual.
  const WEG_ARTEN = new Set(['ruft', 'lesen', 'schreiben']);
  function wegSchritte(i, vor) {
    const liste = vor ? FD.raus[i] : FD.rein[i];
    return liste.filter(k => WEG_ARTEN.has(k.art) && fKanteSichtbar(k)).map(k => ({ k, ziel: vor ? k.n : k.v }));
  }
  // Vorwärts: wer ein erreichtes Ziel überschreibt (rekursiv) und die actual zu einem expect.
  // Rückwärts: was die Funktion überschreibt (rekursiv) und ihr expect; deren Aufrufer landen hier.
  function erweiterung(i, vor) {
    const liste = vor ? FD.rein[i] : FD.raus[i];
    return liste.filter(k => (k.art === 'ueberschreibt' || k.art === 'actual') && (k.sicher || unsicherAn()) && (zustand.mitTests || !FD.fn[k.v].test))
      .map(k => ({ k, ziel: vor ? k.v : k.n }));
  }
  function suche(start, vor, tiefe) {
    const stufe = new Map([[start, 0]]);
    const kanten = [], extra = [];
    const erweitere = (liste, d) => {
      for (let j = 0; j < liste.length; j++) {
        erweiterung(liste[j], vor).forEach(({ k, ziel }) => {
          if (!stufe.has(ziel)) { stufe.set(ziel, d); liste.push(ziel); }
          if (stufe.get(ziel) === d) extra.push(k);
        });
      }
    };
    let rand = [start];
    if (!vor) erweitere(rand, 0);
    for (let d = 0; d < tiefe && rand.length; d++) {
      const neu = [];
      rand.slice().sort((a, b) => a - b).forEach(x => {
        wegSchritte(x, vor).forEach(({ k, ziel }) => {
          if (!stufe.has(ziel)) { stufe.set(ziel, d + 1); neu.push(ziel); }
          if (stufe.get(ziel) === d + 1 && stufe.get(x) === d) kanten.push(k);
        });
      });
      erweitere(neu, d + 1);
      rand = neu;
    }
    return { stufe, kanten, extra };
  }
  function berechneWeg() {
    const w = zustand.weg;
    if (w.art === 'pfad') return pfadErgebnis(w);
    const start = fn(w.start).i, vor = w.richtung === 'vor';
    const voll = suche(start, vor, w.tiefe);
    let tiefe = w.tiefe, ergebnis = voll;
    while (ergebnis.stufe.size > GRENZE_KAESTEN && tiefe > 1) { tiefe--; ergebnis = suche(start, vor, tiefe); }
    let abgeschnitten = 0;
    if (ergebnis.stufe.size > GRENZE_KAESTEN) {
      // Schon Tiefe 1 ist zu groß: die ersten nach Id.
      const behalten = new Set([...ergebnis.stufe.keys()].sort((a, b) => (ergebnis.stufe.get(a) - ergebnis.stufe.get(b)) || (FD.fn[a].id < FD.fn[b].id ? -1 : 1)).slice(0, GRENZE_KAESTEN));
      abgeschnitten = ergebnis.stufe.size - behalten.size;
      [...ergebnis.stufe.keys()].forEach(i => { if (!behalten.has(i)) ergebnis.stufe.delete(i); });
      ergebnis.kanten = ergebnis.kanten.filter(k => ergebnis.stufe.has(k.v) && ergebnis.stufe.has(k.n));
      ergebnis.extra = ergebnis.extra.filter(k => ergebnis.stufe.has(k.v) && ergebnis.stufe.has(k.n));
    }
    return Object.assign(ergebnis, { tiefe, fehlt: voll.stufe.size - ergebnis.stufe.size, abgeschnitten, vor, start });
  }
  // Kürzester Weg zwischen zwei Funktionen („Warum hängt“) nach denselben Regeln, vorwärts.
  function funktionsWeg(von, nach) {
    const a = FD.nachId.get(von), b = FD.nachId.get(nach);
    if (!a || !b) return null;
    const vorgaenger = new Map([[a.i, null]]);
    let rand = [a.i];
    while (rand.length && !vorgaenger.has(b.i)) {
      const neu = [];
      rand.slice().sort((x, y) => FD.fn[x].id < FD.fn[y].id ? -1 : 1).forEach(x => {
        const schritte = wegSchritte(x, true);
        const ziele = [];
        schritte.forEach(s => { ziele.push(s); erweiterung(s.ziel, true).forEach(e => ziele.push({ k: e.k, ziel: e.ziel, ueber: s })); });
        ziele.forEach(s => { if (!vorgaenger.has(s.ziel)) { vorgaenger.set(s.ziel, { von: x, s }); neu.push(s.ziel); } });
      });
      rand = neu;
    }
    if (!vorgaenger.has(b.i)) return null;
    const knoten = [b.i], kanten = [], extra = [];
    let x = b.i;
    while (vorgaenger.get(x)) {
      const v = vorgaenger.get(x);
      if (v.s.ueber) { kanten.push(v.s.ueber.k); extra.push(v.s.k); knoten.push(v.s.ueber.ziel); }
      else kanten.push(v.s.k);
      knoten.push(v.von);
      x = v.von;
    }
    knoten.reverse();
    return { knoten, kanten, extra };
  }
  function pfadErgebnis(w) {
    const weg = funktionsWeg(w.von, w.nach);
    const stufe = new Map();
    if (weg) {
      let d = 0;
      weg.knoten.forEach((i, nr) => {
        // Über ueberschreibt erreichte Funktionen stehen in der Spalte des überschriebenen Ziels.
        if (nr > 0 && weg.extra.some(k => k.v === i && k.n === weg.knoten[nr - 1])) stufe.set(i, d);
        else stufe.set(i, nr === 0 ? 0 : ++d);
      });
    }
    return { stufe, kanten: weg ? weg.kanten : [], extra: weg ? weg.extra : [], tiefe: null, fehlt: 0, abgeschnitten: 0, vor: true, pfad: !!weg, start: fn(w.von) ? fn(w.von).i : null };
  }

  function wegElemente(kanten) {
    const w = berechneWeg();
    zustand.wegErgebnis = w;
    const els = [];
    const rahmen = new Set();
    const ids = [...w.stufe.keys()].sort((a, b) => (w.stufe.get(a) - w.stufe.get(b)) || (FD.fn[a].id < FD.fn[b].id ? -1 : 1));
    ids.forEach(i => {
      const f = FD.fn[i], d = w.stufe.get(i);
      const r = 'fw:' + d + ':' + f.pfad;
      if (!rahmen.has(r)) { rahmen.add(r); els.push({ group: 'nodes', data: { id: r, label: dateiName(f.pfad), typ: 'fnachbar', ref: 'datei:' + f.pfad, pfad: f.pfad } }); }
      els.push(fKasten(f, r, true));
    });
    w.kanten.forEach(k => kanten.add(FD.fn[k.v].id, FD.fn[k.n].id, k.art, k));
    // ueberschreibt/actual stehen in einer Spalte und zählen nicht für das Layout.
    w.extra.forEach(k => { kanten.add(FD.fn[k.v].id, FD.fn[k.n].id, k.art, k); });
    const extraIds = new Set(w.extra.map(k => k.id));
    const alt = kanten.werte;
    kanten.werte = () => alt().map(e => { if (e.data.kanten.every(id => extraIds.has(id))) e.classes = 'ohneLayout'; return e; });
    const ort = new Map(ids.map(i => [i, FD.fn[i].id]));
    grenzErsatz(els, ort, w.kanten.concat(w.extra));
    return els;
  }

  // Klassen, die von Schaltern abhängen (Markierung, detekt), ohne neues Layout.
  function fKlassen() {
    zeigeWegInfo();
    if (zustand.ebene !== 'funktion' || !FD) return;
    const paare = grenzPaare();
    cy.batch(() => {
      cy.elements().removeClass('grenze grenzziel');
      cy.nodes('[typ="funktion"]').forEach(n => n.data('sym', symbolCode(FD.fn[n.data('fi')])));
      cy.edges().forEach(e => {
        const ids = e.data('kanten') || [];
        let b = e.data('befund') ? befundNachId.get(e.data('befund')) : null;
        if (!b) {
          for (const id of ids) {
            const k = FD.kanten[+id.slice(3)];
            if (k && k.art !== 'ueberschreibt' && k.art !== 'actual' && paare.has(FD.fn[k.v].id + '|' + FD.fn[k.n].id)) { b = paare.get(FD.fn[k.v].id + '|' + FD.fn[k.n].id); break; }
          }
        }
        if (b && zustand.markierung) { e.addClass('grenze'); e.target().addClass('grenzziel'); }
      });
    });
  }

  // ---- Zählzeile des Wegmodus
  const weginfo = document.getElementById('weginfo');
  function zeigeWegInfo() {
    const w = zustand.ebene === 'funktion' && zustand.weg ? zustand.wegErgebnis : null;
    document.querySelector('.flaeche').classList.toggle('mitweg', !!w);
    if (!w) { weginfo.hidden = true; weiter.hidden = true; return; }
    const erreicht = [...w.stufe.keys()].filter(i => i !== w.start);
    const dateien = new Set([...w.stufe.keys()].map(i => FD.fn[i].pfad));
    const markiert = erreicht.filter(i => FD.fn[i].markiert).length;
    let text;
    if (zustand.weg.art === 'pfad') {
      text = w.pfad ? 'Weg ' + kurzFunktion(zustand.weg.von) + ' → ' + kurzFunktion(zustand.weg.nach) + ': ' + (w.stufe.size - 1) + ' Schritte über ' + dateien.size + ' Dateien'
        : kurzFunktion(zustand.weg.von) + ' ruft ' + kurzFunktion(zustand.weg.nach) + ' nicht (über ' + (unsicherAn() ? 'sichere und unsichere' : 'sichere') + ' Kanten' + (lesenAn() ? ' mit Lesezugriffen' : '') + ').';
    } else {
      text = 'Wirkungsweg ' + (w.vor ? 'vorwärts' : 'rückwärts') + ' ab ' + kurzFunktion(zustand.weg.start) + ', Tiefe ' + w.tiefe + ': ' + erreicht.length + ' Funktionen in ' + dateien.size + ' Dateien erreicht · davon markiert ' + markiert + ', unmarkiert ' + (erreicht.length - markiert);
      if (w.tiefe < zustand.weg.tiefe) text += ' · Tiefe auf ' + w.tiefe + ' gekürzt (Grenze ' + GRENZE_KAESTEN + ' Kästen), ' + w.fehlt + ' Funktionen bis Tiefe ' + zustand.weg.tiefe + ' nicht gezeigt';
      else if (w.abgeschnitten) text += ' · ' + w.abgeschnitten + ' Funktionen nicht gezeigt (Grenze ' + GRENZE_KAESTEN + ' Kästen)';
    }
    weginfo.innerHTML = `<span>${esc(text)}</span> <button type="button" class="btn" data-zur-datei>Zurück zur Datei</button>`;
    weginfo.querySelector('[data-zur-datei]').addEventListener('click', zurueckZurDatei);
    weginfo.hidden = false;
  }
  async function zurueckZurDatei() {
    const start = zustand.weg ? (zustand.weg.start || zustand.weg.von) : null;
    zustand.weg = null;
    if (start) await zeigeFunktion(start); else await zeigeFunktionsDatei(zustand.fDatei);
  }

  // Ansicht beim Öffnen: alles, wenn es lesbar ist, sonst die eigene Datei bzw. der Start.
  function fStartAnsicht() {
    if (zustand.weg) { wegAnsicht(); return; }
    if (ziel(cy.elements(), 30).zoom >= LESBAR) { einpassen(cy.elements(), 30); return; }
    const kern = zustand.weg ? cy.getElementById(fn(zustand.weg.start || zustand.weg.von) ? fn(zustand.weg.start || zustand.weg.von).id : '') : cy.getElementById('ff:' + zustand.fDatei);
    if (kern.empty()) { einpassen(cy.elements(), 30); return; }
    const v = ziel(kern, 30);
    const zoom = Math.max(v.zoom, Math.min(1, LESBAR * 1.05));
    const bb = kern.boundingBox();
    cy.viewport({ zoom, pan: { x: cy.width() / 2 - zoom * (bb.x1 + bb.w / 2), y: bb.h * zoom <= cy.height() - 60 ? cy.height() / 2 - zoom * (bb.y1 + bb.h / 2) : 40 - zoom * bb.y1 } });
  }

  // Wegmodus beim Öffnen (A09b): eingepasst auf den ganzen Weg, mit Rand und Platz unter der
  // Infoleiste. Der lesbare Mindestzoom des Fokus (MIN_ZOOM_FOKUS) gilt hier nicht. Wäre die Schrift
  // beim Einpassen kleiner als LESBAR (9 px), steht die Startspalte bei diesem Zoom bündig am Rand
  // (vorwärts links, rückwärts rechts), senkrecht um den Start; die Zeile „weiter rechts: N
  // Funktionen“ nennt, was außerhalb liegt. Gewählt nach Proben an Sketchorus, siehe Bericht A09b.
  const RAND_WEG = 30;
  function wegAnsicht() {
    const w = zustand.weg;
    const startId = w ? (fn(w.start || w.von) ? fn(w.start || w.von).id : '') : '';
    const alles = cy.elements();
    if (alles.empty()) return;
    const bb = alles.boundingBox();
    const leiste = document.getElementById('infoleiste');
    const oben = Math.max(RAND_WEG, leiste.offsetTop + leiste.offsetHeight + 14);
    const legende = document.querySelector('.flaeche .legende');
    const unten = Math.max(RAND_WEG, legende && legende.offsetHeight ? legende.offsetHeight + 16 : 0);
    const breite = Math.max(1, cy.width() - 2 * RAND_WEG), hoehe = Math.max(1, cy.height() - oben - unten);
    let zoom = Math.min(MAX_ZOOM_PASSEN, breite / Math.max(1, bb.w), hoehe / Math.max(1, bb.h));
    let pan;
    const start = cy.getElementById(startId);
    if (zoom >= LESBAR || start.empty()) {
      pan = { x: RAND_WEG + (breite - zoom * bb.w) / 2 - zoom * bb.x1, y: oben + (hoehe - zoom * bb.h) / 2 - zoom * bb.y1 };
    } else {
      zoom = LESBAR;
      // Platz für die Zeile „weiter …“ unter der Leiste.
      const oben2 = oben + 30, hoehe2 = Math.max(1, cy.height() - oben2 - unten);
      const spalte = start.parent().nonempty() ? start.parent() : start;
      const sb = spalte.boundingBox(), sp = start.position();
      const links = sp.x <= bb.x1 + bb.w / 2;
      const x = links ? RAND_WEG - zoom * sb.x1 : cy.width() - RAND_WEG - zoom * sb.x2;
      let y;
      if (bb.h * zoom <= hoehe2) y = oben2 + (hoehe2 - zoom * bb.h) / 2 - zoom * bb.y1;
      else {
        y = oben2 + hoehe2 / 2 - zoom * sp.y;
        y = Math.min(oben2 - zoom * bb.y1, Math.max(cy.height() - unten - zoom * bb.y2, y));
      }
      pan = { x, y };
    }
    cy.stop(true, true);
    cy.viewport({ zoom, pan });
    zaehleWeiter();
  }
  // Zeile „weiter rechts: N Funktionen“: Funktionen des Wegs, die nicht ganz im Bild liegen.
  const weiter = document.getElementById('weiter');
  function zaehleWeiter() {
    if (zustand.ebene !== 'funktion' || !zustand.weg) { weiter.hidden = true; return; }
    const b = cy.width(), h = cy.height();
    let rechts = 0, links = 0, sonst = 0;
    cy.nodes('[typ="funktion"]').forEach(n => {
      const r = n.renderedBoundingBox({ includeLabels: false });
      if (r.x2 > b) rechts++;
      else if (r.x1 < 0) links++;
      else if (r.y1 < 0 || r.y2 > h) sonst++;
    });
    const fkt = n => n + (n === 1 ? ' Funktion' : ' Funktionen');
    const teile = [];
    if (rechts) teile.push('weiter rechts: ' + fkt(rechts));
    if (links) teile.push('weiter links: ' + fkt(links));
    if (sonst) teile.push('darüber oder darunter: ' + fkt(sonst));
    weiter.textContent = teile.join(' · ');
    weiter.hidden = !teile.length;
  }
  let weiterBild = 0;
  cy.on('viewport', () => { if (!weiterBild) weiterBild = requestAnimationFrame(() => { weiterBild = 0; zaehleWeiter(); }); });

  // ---- Öffnen
  async function zeigeFunktionsDatei(pfad, opt) {
    fdaten();
    zustand.ebene = 'funktion';
    if (pfad !== zustand.fDatei) zustand.fAuf = new Set();
    zustand.fDatei = pfad;
    zustand.zuletztDatei = pfad;
    zustand.weg = null;
    const eigene = (FD.nachDatei.get(pfad) || []).map(i => FD.fn[i]);
    if (eigene.some(f => f.test) && !eigene.some(f => !f.test) && !zustand.mitTests) zustand.mitTests = true;
    if (!opt || !opt.ohneAuswahl) setzeAuswahl({ art: 'fdatei', id: pfad });
    if (veraltet()) await zeichne();
    leeren();
    if (!opt || !opt.ohneAuswahl) dateiFunktionenSeite(pfad);
  }
  async function zeigeFunktion(id, opt) {
    const f = fn(id);
    if (!f) return;
    if (zustand.weg && !cy.getElementById(id).nonempty()) zustand.weg = null;
    if (!zustand.weg) {
      if (f.pfad !== zustand.fDatei) zustand.fAuf = new Set();
      zustand.fDatei = f.pfad;
    }
    zustand.zuletztDatei = f.pfad;
    zustand.ebene = 'funktion';
    if (f.test && !zustand.mitTests) zustand.mitTests = true;
    setzeAuswahl({ art: 'funktion', id });
    if (veraltet()) await zeichne();
    // Liegt die Funktion in einer zusammengefassten Nachbardatei, wird diese aufgeklappt.
    if (!zustand.weg && cy.getElementById(id).empty() && cy.getElementById('fz:' + f.pfad).nonempty()) {
      zustand.fAuf.add(f.pfad);
      await zeichne();
    }
    if (!opt || !opt.ohneFokus) hebeFunktionHervor(id);
    funktionsDetails(id);
  }
  function hebeFunktionHervor(id, opt) {
    const f = fn(id);
    const o = Object.assign({ titel: kurzFunktion(id) }, opt);
    if (cy.getElementById(id).nonempty()) fokus([id], o);
    else if (f && cy.getElementById('fz:' + f.pfad).nonempty()) fokus(['fz:' + f.pfad], o);
    else leeren();
    zeigeWegInfo();
  }
  async function zeigeWeg(id, richtung, tiefe) {
    const f = fn(id);
    if (!f) return;
    zustand.ebene = 'funktion';
    zustand.fDatei = zustand.fDatei || f.pfad;
    zustand.fTiefe = tiefe;
    const neuerStart = !zustand.weg || zustand.weg.art !== 'weg' || zustand.weg.start !== id;
    zustand.weg = { art: 'weg', start: id, richtung, tiefe };
    if (neuerStart) zustand.wegLesen = f.markiert ? true : zustand.fLesen;
    setzeAuswahl({ art: 'funktion', id });
    if (veraltet()) await zeichne();
    // Start gewählt, aber ohne Fluss und ohne Fokus-Zoom: Die Ansicht zeigt den ganzen Weg.
    hebeFunktionHervor(id, { ohneFluss: true, ohneZoom: true });
    wegAnsicht();
    funktionsDetails(id);
  }
  async function zeigeFunktionsPfad(von, nach) {
    fdaten();
    zustand.ebene = 'funktion';
    zustand.weg = { art: 'pfad', von, nach };
    zustand.wegLesen = zustand.fLesen;
    zustand.fDatei = zustand.fDatei || fn(von).pfad;
    setzeAuswahl({ art: 'pfad', von, nach, ebene: 'funktion' });
    if (veraltet()) await zeichne();
    leeren();
    zeigeWegInfo();
    const w = zustand.wegErgebnis;
    if (w.pfad) {
      const nks = cy.nodes('[typ="funktion"]');
      nks.addClass('hl');
      cy.getElementById(fn(von).id).addClass('gewaehlt');
      fluss.start(cy.edges().not('.ohneLayout'));
    }
    funktionsDetails(von);
    return w.pfad ? [...w.stufe.keys()].map(i => FD.fn[i].id) : null;
  }
  async function zeigeGrenze(befundId) {
    const b = befundNachId.get(befundId);
    if (!b) return;
    const von = fn(b.beleg.von);
    if (!von) return;
    if (!zustand.markierung) { zustand.markierung = true; document.getElementById('u-markierung').checked = true; }
    if (b.beleg.unsicher && !zustand.fUnsicher) zustand.fUnsicher = true;
    // Grenzkante nur über Lesezugriffe (Getter/Setter): Schalter „Lesezugriffe“ einschalten.
    const nachF = fn(b.beleg.nach);
    const direkt = nachF ? FD.raus[von.i].filter(k => k.n === nachF.i) : [];
    if (direkt.length && !direkt.some(k => k.art === 'ruft') && direkt.some(k => k.art === 'lesen' || k.art === 'schreiben')) zustand.fLesen = true;
    zustand.ebene = 'funktion';
    zustand.weg = null;
    if (von.pfad !== zustand.fDatei) zustand.fAuf = new Set();
    zustand.fDatei = von.pfad;
    setzeAuswahl({ art: 'grenze', id: befundId });
    if (veraltet()) await zeichne();
    const nach = fn(b.beleg.nach);
    if (nach && cy.getElementById(nach.id).empty() && cy.getElementById('fz:' + nach.pfad).nonempty()) { zustand.fAuf.add(nach.pfad); await zeichne(); }
    const e = cy.edges('.grenze').filter(x => x.source().id() === von.id && (x.target().id() === b.beleg.nach || x.target().id() === 'fz:' + (nach ? nach.pfad : '')));
    if (e.nonempty()) {
      hebeKanteHervor(e[0]);
      // Lesbar auf die markierte Funktion zoomen; lange Kanten in großen Dateien wären sonst winzig.
      fahre(fokusZiel(e[0].source(), e[0].connectedNodes(), 80));
      fKanteDetails(e[0]);
    } else { hebeFunktionHervor(von.id); befundDetails(b); }
  }

  // ---- Seitenleiste
  const kf = (id, text) => fn(id) ? `<button type="button" class="zur" data-funktion="${esc(id)}">${esc(text || kurzFunktion(id))}</button>` : `<code>${esc(text || kurzFunktion(id))}</code>`;
  function signatur(f) {
    const params = (f.params || []).map((t, i) => ((f.vararg || []).includes(i) ? 'vararg ' : '') + (t === null ? '?' : t) + ((f.vorgabe || []).includes(i) ? ' = …' : ''));
    const name = f.name.replace(/\/\d+.*$/, '').replace(/^\[[^\]]*\]/, '');
    const teile = [f.sicht].concat(f.mods || []);
    if (f.c) return 'C: ' + name + '(' + (f.kurz.split('/')[1] || '') + ' Parameter)';
    return teile.join(' ') + ' fun ' + (f.erw ? f.erw + '.' : '') + name + '(' + params.join(', ') + ')';
  }
  const TRAEGER_TEXT = { funktion: 'an der Funktion', klasse: 'an der Klasse', datei: 'an der Datei' };
  // Unsicheres Ziel: die anderen Kandidaten derselben Aufrufstelle (gleicher Aufrufer, gleicher
  // Name, unsicher).
  function andereKandidaten(k) {
    const name = n => FD.fn[n].name.replace(/\/.*$/, '');
    return FD.raus[k.v].filter(x => x !== k && !x.sicher && x.art === k.art && name(x.n) === name(k.n)).map(x => FD.fn[x.n].id);
  }
  function aufrufZeile(k, gegen) {
    const quelle = FD.fn[k.v];
    const ort = k.zeile ? `<span class="ort">${esc(dateiName(quelle.pfad))}:${k.zeile}</span> ${editorKnopf(quelle.pfad, k.zeile, true)}` : '';
    const merkmale = [ART_TEXT[k.art] || k.art];
    if (k.herkunft) merkmale.push(k.herkunft);
    if (k.gewicht > 1) merkmale.push(k.gewicht + '×');
    if (FD.fn[k.v].test) merkmale.push('Test');
    let unsicher = '';
    if (!k.sicher) {
      const andere = andereKandidaten(k);
      unsicher = ` <span class="chip warn" title="unsicher">unsicher${k.grund ? ': ' + esc(k.grund) : ''}</span>${andere.length ? `<br><span class="leer">andere Kandidaten: ${andere.map(id => kf(id)).join(', ')}</span>` : ''}`;
    }
    return `<li>${kf(FD.fn[gegen].id)} ${ort} <span class="leer">${esc(merkmale.join(' · '))}</span>${unsicher}</li>`;
  }
  function aufrufListe(liste, gegen, leer) {
    if (!liste.length) return `<p class="leer">${esc(leer)}</p>`;
    const sortiert = liste.slice().sort((a, b) => (a.sicher === b.sicher ? 0 : a.sicher ? -1 : 1) || (FD.fn[gegen(a)].id < FD.fn[gegen(b)].id ? -1 : 1));
    const html = `<ul class="liste kette">${sortiert.map(k => aufrufZeile(k, gegen(k))).join('')}</ul>`;
    return sortiert.length > 40 ? `<details><summary>${sortiert.length} zeigen</summary>${html}</details>` : html;
  }
  function funktionsDetails(id) {
    const f = fn(id);
    if (!f) { uebersicht(); return; }
    const chips = [];
    if (f.markiert) chips.push(`<span class="chip warn" title="markiert">⛨ markiert${f.markierung ? ' · ' + esc(f.markierung[0].split('.').pop()) + ' ' + esc(TRAEGER_TEXT[f.markierung[1]]) : ''}</span>`);
    if (f.ausnahme) chips.push('<span class="chip adr">Ausnahme</span>');
    if (f.ohneKoerper) chips.push('<span class="chip">ohne Körper</span>');
    if (f.implizit) chips.push('<span class="chip">implizit</span>');
    if (f.test) chips.push('<span class="chip warn">Test</span>');
    const annot = (f.annot || []).map(([n, s]) => `<li><code>@${esc(n)}</code>${s ? '' : ' <span class="leer">nicht aufgelöst</span>'}</li>`).join('');
    const zeilen = [
      ['Zeilen (ohne Leerzeilen)', f.zeilen], ['Komplexität', f.komplex === null ? '–' : f.komplex],
      ['Fan-in sicher · mit unsicheren', f.fanIn + ' · ' + f.fanInU], ['Fan-out sicher · mit unsicheren', f.fanOut + ' · ' + f.fanOutU],
      ['externe Aufrufe', f.extern]
    ];
    if (f.delegiert !== null && f.delegiert !== undefined) zeilen.push(['delegierte Eigenschaften gelesen', f.delegiert]);
    const rein = FD.rein[f.i].filter(k => k.art !== 'ueberschreibt' && k.art !== 'actual' && (zustand.mitTests || !FD.fn[k.v].test));
    const raus = FD.raus[f.i].filter(k => k.art !== 'ueberschreibt' && k.art !== 'actual');
    const ueber = FD.raus[f.i].filter(k => k.art === 'ueberschreibt' || k.art === 'actual');
    const ueberVon = FD.rein[f.i].filter(k => k.art === 'ueberschreibt' || k.art === 'actual');
    const bf = M.befunde.filter(b => befundSichtbar(b) && (istMarkierung(b) ? b.beleg.von === id || b.beleg.nach === id || b.beleg.kette.some(e => e.funktion === id) : b.knoten.includes(id)));
    const tiefe = zustand.weg && zustand.weg.tiefe ? zustand.weg.tiefe : zustand.fTiefe;
    const weg = `<div><h3 class="quelle-m">Wirkungsweg <em>Tiefe</em></h3><div class="wegknoepfe"><button type="button" class="btn" data-weg="vor">Wirkungsweg vorwärts</button><button type="button" class="btn" data-weg="rueck">rückwärts</button><label>Tiefe <select id="weg-tiefe">${[1, 2, 3, 4, 5].map(n => `<option${n === tiefe ? ' selected' : ''}>${n}</option>`).join('')}</select></label></div>${zustand.weg ? '<p style="margin-top:6px"><button type="button" class="zur" data-zur-datei>← Zurück zur Datei</button></p>' : ''}</div>`;
    seite.innerHTML = `<button type="button" class="zur" data-zur-datei-seite>← ${esc(dateiName(f.pfad))}</button>
      <div><div class="kopfzeile"><h2>${esc(f.kurz)}</h2><div class="symbole">${editorKnopf(f.pfad, f.von)}</div></div>
      <p class="pfad"><code>${esc(signatur(f))}</code></p>
      <p class="pfad">${esc(f.pfad)}:${f.von}${f.bis !== f.von ? '–' + f.bis : ''}</p>${chips.length ? `<div class="chips" style="margin-top:6px">${chips.join('')}</div>` : ''}</div>
      ${beschreibungHtml(id)}
      ${weg}
      ${annot ? `<div><h3 class="quelle-m">Annotationen <em>${f.annot.length}</em></h3><ul class="liste">${annot}</ul></div>` : ''}
      <div><h3 class="quelle-m">Messwerte <em>gemessen · daidalos.json</em></h3><table>${zeilen.map(([a, b]) => `<tr><td>${esc(a)}</td><td>${esc(b)}</td></tr>`).join('')}</table></div>
      <div><h3 class="quelle-m">Gerufen von <em>${rein.length}</em></h3>${aufrufListe(rein, k => k.v, 'niemandem (intern)')}</div>
      <div><h3 class="quelle-m">Ruft <em>${raus.length}</em></h3>${aufrufListe(raus, k => k.n, 'keine interne Funktion')}</div>
      ${ueber.length || ueberVon.length ? `<div><h3 class="quelle-m">Überschreibt · actual</h3><ul class="liste">${ueber.map(k => `<li>${esc(ART_TEXT[k.art])} ${kf(FD.fn[k.n].id)}${k.sicher ? '' : ' <span class="chip warn">unsicher</span>'}</li>`).join('')}${ueberVon.map(k => `<li>${k.art === 'actual' ? 'actual' : 'überschrieben von'} ${kf(FD.fn[k.v].id)}${k.sicher ? '' : ' <span class="chip warn">unsicher</span>'}</li>`).join('')}</ul></div>` : ''}
      ${bf.length ? `<div><h3 class="quelle-m">Befunde an dieser Funktion <em>${bf.length}</em></h3><ol class="befunde">${bf.map(b => befundKnopf(b, '!')).join('')}</ol></div>` : ''}`;
    verdrahte();
    seite.querySelectorAll('[data-weg]').forEach(b => b.addEventListener('click', () => zeigeWeg(id, b.dataset.weg, +document.getElementById('weg-tiefe').value)));
    document.getElementById('weg-tiefe').addEventListener('change', e => {
      zustand.fTiefe = +e.target.value;
      if (zustand.weg && zustand.weg.art === 'weg') zeigeWeg(zustand.weg.start, zustand.weg.richtung, zustand.fTiefe);
    });
    seite.querySelectorAll('[data-zur-datei]').forEach(b => b.addEventListener('click', zurueckZurDatei));
    seite.querySelectorAll('[data-zur-datei-seite]').forEach(b => b.addEventListener('click', async () => {
      if (zustand.weg) { zustand.weg = null; }
      await zeigeFunktionsDatei(f.pfad);
    }));
  }
  // Seitenleiste ohne gewählte Funktion: die Datei mit ihren Funktionen nach Zeile.
  function dateiFunktionenSeite(pfad) {
    const eigene = (FD.nachDatei.get(pfad) || []).map(i => FD.fn[i]).sort((a, b) => a.von - b.von || (a.id < b.id ? -1 : 1));
    const dateiId = 'datei:' + pfad;
    const zu = zustand.fZu && zustand.fZu.size ? `<p class="leer" style="margin-top:6px">${zustand.fZu.size} Nachbardateien zusammengefasst (Grenze ${GRENZE_KAESTEN} Kästen); ein Klick klappt eine auf.</p>` : '';
    // Klassen als Überschrift, sobald sich der Behälter ändert (nach Zeile sortiert).
    let zuletzt = null;
    const kopf = f => {
      if (f.behaelter === zuletzt) return '';
      zuletzt = f.behaelter;
      if (!f.behaelter) return '<li class="leer">oberste Ebene</li>';
      const k = (FD.klassen.get(pfad) || new Map()).get(f.behaelter);
      const teile = f.behaelter.split('.');
      return `<li class="leer" style="padding-left:${(teile.length - 1) * 12}px">${esc(k ? KLASSEN_ART[k.art] || k.art : 'Klasse')} <code>${esc(f.behaelter)}</code></li>`;
    };
    const liste = eigene.map(f => kopf(f) + `<li style="padding-left:${(f.behaelter ? f.behaelter.split('.').length : 0) * 12}px">${f.markiert ? '<span title="markiert">⛨</span> ' : ''}${kf(f.id, f.name)} <span class="ort">${f.von}</span>${f.komplex !== null ? ` <span class="leer">K ${f.komplex}</span>` : ''}${f.ohneKoerper ? ' <span class="leer">ohne Körper</span>' : ''}</li>`).join('');
    seite.innerHTML = `<button type="button" class="zur" data-knoten="${esc(dateiId)}">← Dateiebene</button>
      <div><div class="kopfzeile"><h2>${esc(dateiName(pfad))}</h2><div class="symbole">${editorKnopf(pfad, 1)}</div></div><p class="pfad">${esc(pfad)} · Funktionsebene</p>${zu}</div>
      ${knoten.has(dateiId) ? beschreibungHtml(dateiId) : ''}
      <div><h3 class="quelle-m">Funktionen <em>${eigene.length}</em></h3>${eigene.length ? `<ul class="liste kette">${liste}</ul>` : '<p class="leer">Keine Funktionen in dieser Datei.</p>'}</div>
      <div><p class="leer">Links stehen Aufrufer aus anderen Dateien, rechts Gerufene. Klick auf eine Funktion zeigt Signatur, Aufrufe und Wirkungsweg; Doppelklick auf eine fremde Funktion öffnet deren Datei.</p></div>`;
    verdrahte();
  }
  // Seitenleiste ohne Datei: um eine Datei bitten.
  function bitteUmDatei() {
    const dateien = [...fdaten().nachDatei.keys()].sort();
    seite.innerHTML = `<div><h2>Funktionsebene</h2><p class="leer">Die Funktionsebene zeigt immer eine Datei. Wähle eine Datei: Doppelklick auf der Dateiebene, Knopf „Funktionen“ in ihrer Seitenleiste oder hier.</p></div>
      <div><input type="search" class="suche" id="f-datei" list="f-dateien" placeholder="Datei" aria-label="Datei" autocomplete="off"> <button type="button" class="btn" id="f-oeffnen">Öffnen</button><datalist id="f-dateien">${dateien.map(p => `<option value="${esc(p)}"></option>`).join('')}</datalist><p class="leer" id="f-fehler" style="margin-top:6px"></p></div>`;
    const los = () => {
      const t = document.getElementById('f-datei').value.trim();
      const treffer = dateien.filter(p => p === t || p.endsWith('/' + t) || p.toLowerCase().includes(t.toLowerCase()));
      const genau = dateien.find(p => p === t) || (treffer.length === 1 ? treffer[0] : null);
      if (genau) zeigeFunktionsDatei(genau);
      else document.getElementById('f-fehler').textContent = treffer.length ? treffer.length + ' Dateien passen' : 'Keine Datei mit Funktionen passt.';
    };
    document.getElementById('f-oeffnen').addEventListener('click', los);
    document.getElementById('f-datei').addEventListener('keydown', e => { if (e.key === 'Enter') los(); });
  }

  function fKanteDetails(e) {
    const d = e.data();
    const ks = (d.kanten || []).map(id => FD.kanten[+id.slice(3)]).filter(Boolean);
    let html = `<button type="button" class="zur" data-zur-datei-seite>← ${esc(dateiName(zustand.fDatei || ''))}</button>`;
    const b = d.befund ? befundNachId.get(d.befund) : null;
    if (!ks.length && b) {
      html += `<div><h2>Grenzkante</h2><p class="pfad">${b ? esc(befundTitel(b)) : ''}</p></div><div><p>${kf(b.beleg.von)} ruft unmarkiert ${kf(b.beleg.nach)} über ueberschreibt/actual.</p><ol class="befunde" style="margin-top:8px">${befundKnopf(b, '!')}</ol></div>`;
    } else {
      const titel = ks.length === 1 ? kf(FD.fn[ks[0].v].id) + ' → ' + kf(FD.fn[ks[0].n].id) : esc(name(e.source().data('ref'))) + ' → ' + esc(name(e.target().data('ref')));
      html += `<div><h2>${titel}</h2><p class="pfad">${esc(ART_TEXT[d.art] || d.art)}${d.verdichtet ? ' · zusammengefasst aus ' + ks.length + ' Kanten' : ''}</p></div>`;
      html += `<div><h3 class="quelle-m">Aufrufe <em>gemessen · daidalos.json</em></h3><ul class="liste kette">${ks.map(k => aufrufZeile(k, k.n)).join('')}</ul><p class="leer" style="margin-top:6px">Je Kante die erste Aufrufstelle; alle Stellen stehen in daidalos.json und in daidalos aufrufe.</p></div>`;
      const paare = grenzPaare();
      const gb = ks.map(k => paare.get(FD.fn[k.v].id + '|' + FD.fn[k.n].id)).filter(Boolean);
      if (gb.length) html += `<div><h3 class="quelle-m">Markierung verlassen <em>${gb.length}</em></h3><ol class="befunde">${gb.map(x => befundKnopf(x, '!')).join('')}</ol></div>`;
    }
    seite.innerHTML = html;
    verdrahte();
    seite.querySelectorAll('[data-zur-datei-seite]').forEach(x => x.addEventListener('click', () => { zustand.weg = null; zeigeFunktionsDatei(zustand.fDatei); }));
  }

  // ------------------------------------------------------------ Start
  let gemerkt = null;
  try { gemerkt = localStorage.getItem('daidalos-thema'); } catch (e) { /* ohne Speicher */ }
  document.querySelectorAll('.thema button').forEach(b => b.addEventListener('click', () => setzeThema(b.dataset.thema)));
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => cy.style(stil()));
  setzeThema(['dark', 'light', 'system'].includes(gemerkt) ? gemerkt : 'dark');

  // Kopfzeile
  document.getElementById('projekt').textContent = M.ziel.name;
  const stand = document.getElementById('stand');
  const commit = M.ziel.git_commit ? 'Commit ' + M.ziel.git_commit.slice(0, 7) : 'ohne Git-Commit';
  stand.textContent = commit + ' · ' + gruppen.filter(g => g.art === 'modul').length + ' Module · ' + kartenDateien.length + ' Dateien auf der Karte';
  document.getElementById('aenderungen').hidden = !M.ziel.git_aenderungen;

  // Für Tests und spätere Erweiterungen.
  window.daidalos = {
    cy, zustand, zeiten, zeichne, zeigeBefund, zeigeKnoten, zeigeKante, zeigePfad, sucheWeg, editorLink,
    zeigeFunktion, zeigeFunktionsDatei, zeigeWeg, zeigeFunktionsPfad, zeigeGrenze, fdaten, positionsEbene,
    funktionsBlockGelesen: () => FD !== null, GRENZE_KAESTEN, LESBAR, WEG_ELK, wegAnsicht,
    kartenDateien, gross, SAMMEL, MIN_ZOOM_FOKUS, sperre, sperren, speicherName,
    fluss: () => fluss.stand(),
    letzterLink: () => letzterLink
  };
  leseAdresse();
})();
