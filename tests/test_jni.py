from __future__ import annotations

import pytest

from daidalos.adapter.jni import dekodiere, finde_c_funktionen, jni_name, kodiere


@pytest.mark.parametrize(
    ("klasse", "methode", "erwartet"),
    [
        ("de.a.Insel", "rechne", "Java_de_a_Insel_rechne"),
        ("de.a.Insel", "rechne_schnell", "Java_de_a_Insel_rechne_1schnell"),
        ("de.a.B$C", "f", "Java_de_a_B_00024C_f"),
        ("de.a.Ä", "f", "Java_de_a__000c4_f"),
    ],
)
def test_kodieren_und_dekodieren(klasse: str, methode: str, erwartet: str) -> None:
    assert jni_name(klasse, methode) == erwartet
    name = dekodiere(erwartet)
    assert name is not None
    assert (name.klasse, name.methode, name.signatur) == (klasse, methode, None)


def test_escapes_2_und_3() -> None:
    assert kodiere("[Ljava/lang/String;") == "_3Ljava_lang_String_2"


def test_ueberladung_mit_signatur() -> None:
    name = dekodiere("Java_de_a_Insel_f__Ljava_lang_String_2I")
    assert name is not None
    assert (name.klasse, name.methode, name.signatur) == ("de.a.Insel", "f", "Ljava/lang/String;I")


def test_kein_jni_name() -> None:
    assert dekodiere("hilfe") is None
    assert dekodiere("Java_nurEins") is None


def test_c_funktionen_nur_definitionen() -> None:
    quelle = b"""#include <jni.h>
JNIEXPORT jint JNICALL Java_de_a_Insel_eins(JNIEnv *env, jobject s);
JNIEXPORT jint JNICALL
Java_de_a_Insel_zwei(JNIEnv *env, jobject s) { return 0; }
static int hilfe(void) { return 1; }
/* Java_de_a_Insel_kommentar(void) {} */
"""
    funktionen = finde_c_funktionen(quelle)
    assert [(f.name, f.zeile) for f in funktionen] == [("Java_de_a_Insel_zwei", 4)]
