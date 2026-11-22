#include <jni.h>

/* Gegenstück zu Insel.rechne_schnell; "_" im Namen wird zu "_1". */
JNIEXPORT jint JNICALL
Java_beispiel_nativ_Insel_rechne_1schnell(JNIEnv *env, jobject self, jint a) {
    return a;
}
