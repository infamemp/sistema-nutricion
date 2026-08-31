"""
Autenticacion del sistema.

Un solo usuario (Marifer), una sola contraseña. Nada de tabla de
usuarios ni registro, no hace falta para un sistema de un operador.

La contraseña nunca se guarda en texto plano. Se guarda como un hash
con sal, usando PBKDF2 (modulo hashlib de la libreria estandar, sin
dependencias externas).

Como generar la contraseña por primera vez o cambiarla:
    python auth.py
Esto pregunta la contraseña sin mostrarla en pantalla, y devuelve el
hash listo para pegar en el archivo .env como MARIFER_PASSWORD_HASH.

La contraseña en si NUNCA debe compartirse fuera del servidor.
"""

import hashlib
import hmac
import os

ITERACIONES = 200_000


def generar_hash(password):
    """Crea un hash con sal aleatoria. Formato: sal_hex:hash_hex"""
    sal = os.urandom(16)
    derivado = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sal, ITERACIONES)
    return sal.hex() + ":" + derivado.hex()


def verificar_password(password, hash_guardado):
    """Compara una contraseña contra el hash guardado en .env."""
    if not hash_guardado or ":" not in hash_guardado:
        return False

    sal_hex, hash_hex = hash_guardado.split(":", 1)
    try:
        sal = bytes.fromhex(sal_hex)
        esperado = bytes.fromhex(hash_hex)
    except ValueError:
        return False

    calculado = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sal, ITERACIONES)

    # compare_digest evita que un atacante deduzca el hash midiendo
    # cuanto tarda la comparacion caracter por caracter.
    return hmac.compare_digest(calculado, esperado)


if __name__ == "__main__":
    import getpass

    print("Generar hash de contraseña para MARIFER_PASSWORD_HASH")
    print("(no se muestra en pantalla mientras escribes)")
    print()

    p1 = getpass.getpass("Nueva contraseña: ")
    p2 = getpass.getpass("Confírmala: ")

    if p1 != p2:
        print()
        print("Las contraseñas no coinciden. Intenta de nuevo.")
    elif len(p1) < 8:
        print()
        print("Usa al menos 8 caracteres.")
    else:
        print()
        print("Copia esta línea completa a tu archivo .env:")
        print()
        print("MARIFER_PASSWORD_HASH=" + generar_hash(p1))
