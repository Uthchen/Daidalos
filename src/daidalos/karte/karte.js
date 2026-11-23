/* Daidalos-Karte. Liest die eingebettete Messung (daidalos.json), Deutung (deutung.json) und
   Einstellungen und zeichnet sie mit Cytoscape.js und ELK. Rechnet nichts Neues aus, nur
   Darstellung: Layout, Verdichtung eingeklappter Teile, Hervorhebung, Wegsuche über die Kanten.

   Aufbau:
   1. Daten und Index      5. Stil                  9. Bedienung und Start
   2. Zustand              6. Hervorheben, Fokus    10. Sperren und Positionen
   3. Elemente je Ebene    7. Seitenleiste          11. Pfad-Suche
   4. Zeichnen und Layout  8. Sprungadressen        12. Editor-Links */
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

  function name(id) {
    if (id === SAMMEL) return 'Weitere Ordner';
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
    offen: new Set(),          // ausgeklappte Module auf der Dateiebene (nur bei großen Projekten)
    zuletztModul: null,
    // Kantenführung: 'elk' (ELKs orthogonale Führung), 'taxi' oder 'bezier'; siehe Bericht A05.
    kantenfuehrung: 'elk',
    auswahl: null              // { art: 'knoten' | 'befund' | 'kante' | 'pfad', … }
  };
  const ARTEN_JE_EBENE = { modul: ['gradle', 'nutzt'], paket: ['nutzt'], datei: ['nutzt', 'jni'] };

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

  // Zeichnet die aktuelle Ebene neu. Liefert ein Promise, das nach dem Layout erfüllt ist.
  let gezeichnet = null;
  // Passt die gezeichnete Karte nicht mehr zum Zustand (Ebene, Schalter, ausgeklappte Module)?
  const veraltet = () => layoutSchluessel() !== gezeichnet || cy.nodes().empty();
  function zeichne() {
    const nr = ++lauf;
    const schluessel = layoutSchluessel();
    gezeichnet = schluessel;
    const beginn = performance.now();
    fluss.stopp();
    document.documentElement.dataset.zustand = 'rechnet';
    cy.batch(() => { cy.elements().remove(); cy.add(elemente()); });
    cy.style(stil());
    zeigeSchalter();
    return new Promise(fertig => {
      const ende = () => {
        if (nr !== lauf) return fertig(false);
        wendePositionenAn();
        sperren();
        if (zustand.ebene === 'datei' && !zustand.auswahl) startAnsicht(); else einpassen(cy.elements(), 30);
        if (!gespeichert) zeiten[schluessel] = Math.round(performance.now() - beginn);
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
      const layout = cy.layout({
        name: 'elk', fit: false, animate: false, nodeDimensionsIncludeLabels: false,
        useElkEdgeGeometry: elk,
        elk: Object.assign({}, ELK, elk ? { 'elk.edgeRouting': 'ORTHOGONAL' } : {}),
        nodeLayoutOptions: n => n.isParent() ? Object.assign({}, BEHAELTER_OPTIONEN) : undefined
      });
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
    regeln.push({ selector: 'edge.trenn', style: { 'line-color': tok('--crit'), 'target-arrow-color': tok('--crit'), width: 6, opacity: 1, label: 'data(trennText)', color: tok('--crit'), 'font-weight': 700, 'font-size': 12 } });
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
    return b.regel;
  }
  function befundBeleg(b) {
    if (b.regel === 'zyklus') return b.beleg.knoten.map(name).join(' · ');
    if (b.regel === 'jni-ohne-gegenstueck') return b.beleg.funktion + ' (' + (b.beleg.seite === 'c' ? 'C' : 'Kotlin') + ', Zeile ' + b.beleg.zeile + ')';
    if (b.regel === 'unaufgeloest') return name(b.knoten[0]) + ': ' + b.beleg.importe.map(i => i.import).join(', ');
    return b.knoten.map(name).join(', ');
  }
  const farbe = b => b.regel === 'zyklus' ? 'crit' : 'warn';

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
    const mitDeutung = D.einschaetzungen.map(e => befundNachId.get(e.befund)).filter(Boolean);
    const rest = M.befunde.filter(b => !einschaetzung.has(b.id));
    const rang = { zyklus: 0, 'jni-ohne-gegenstueck': 1, unaufgeloest: 2 };
    rest.sort((a, b) => (rang[a.regel] ?? 3) - (rang[b.regel] ?? 3) ||
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
    const bf = M.befunde.filter(b => b.knoten.includes(id));
    const symbole = k.art === 'datei' ? `<div class="symbole"><button type="button" disabled title="Code-Ansicht kommt mit daidalos serve">${SVG_CODE}Code</button>${editorKnopf(k.pfad, 1)}</div>` : '';
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
    } else if (b.regel === 'unaufgeloest') {
      const d = knoten.get(b.knoten[0]);
      mess += `<p>${kn(b.knoten[0])}</p><ul class="liste">${beleg.importe.map(i => `<li><code>${esc(i.import)}</code> <span class="leer">Zeile ${i.zeile}</span> ${d ? editorKnopf(d.pfad, i.zeile, true) : ''}</li>`).join('')}</ul>`;
    }
    html += `<div><h3 class="quelle-m">Beleg <em>gemessen · daidalos.json</em></h3><div class="mess">${mess}</div></div>`;
    seite.innerHTML = html;
    verdrahte();
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
    else if (k.art === 'datei') zustand.zuletztModul = behaelter(k);
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
    else hash = a.art + '=' + encodeURIComponent(a.id);
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
      if (ebene && ARTEN_JE_EBENE[ebene]) zustand.ebene = ebene;
      if (p.get('befund') && befundNachId.has(p.get('befund'))) { await zeigeBefund(p.get('befund')); return; }
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
    else if (a.art === 'pfad') await zeigePfad(a.von, a.nach);
  }

  async function neuZeichnen() {
    await zeichne();
    await wendeAuswahlAn();
  }

  document.querySelectorAll('#ebenen button').forEach(b => b.addEventListener('click', async () => {
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
  document.getElementById('u-zyklen').addEventListener('change', e => { zustand.zyklen = e.target.checked; cy.style(stil()); });
  document.getElementById('einpassen').addEventListener('click', () => passen(cy.elements(), 30));
  document.getElementById('zuruecksetzen').addEventListener('click', async () => {
    loeschePositionen(zustand.ebene);
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
    setzeAuswahl({ art: 'kante', id: k.id(), ebene: zustand.ebene });
    hebeKanteHervor(k);
    kanteDetails(k);
  });
  cy.on('dbltap', 'node', async e => {
    const n = e.target, ref = n.data('ref'), typ = n.data('typ');
    if (symbolGetroffen(n, e.position)) return;
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
  function aufheben() { zustand.auswahl = null; leeren(); uebersicht(); schreibeAdresse(); }
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
  function wendePositionenAn() {
    const pos = lesePositionen(zustand.ebene);
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
    const pos = lesePositionen(zustand.ebene);
    blattVon(n).forEach(x => { if (!vorZiehen || !vorZiehen.has(x.id())) { const p = x.position(); pos[x.id()] = [Math.round(p.x * 10) / 10, Math.round(p.y * 10) / 10]; } });
    schreibePositionen(zustand.ebene, pos);
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
    const treffer = [...pfadListe.entries()].filter(([s]) => s.toLowerCase().includes(klein));
    if (treffer.length === 1) return { id: treffer[0][1] };
    return { fehler: treffer.length ? '„' + t + '“ passt auf ' + treffer.length + ' Knoten' : 'kein Knoten passt zu „' + t + '“' };
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
    kartenDateien, gross, SAMMEL, MIN_ZOOM_FOKUS, sperre, sperren, speicherName,
    fluss: () => fluss.stand(),
    letzterLink: () => letzterLink
  };
  leseAdresse();
})();
