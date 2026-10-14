// The API answers in English; the interface speaks Spanish. Known messages are translated here,
// anything else falls back to a generic line rather than leaking English to the user.

export const SLOT_TAKEN = 'Ese horario acaba de ser tomado. Elige otro.'
const GENERIC = 'Algo salió mal. Inténtalo de nuevo.'

const EXACT: Record<string, string> = {
  'That slot was just taken': SLOT_TAKEN,
  'Reservation is already cancelled': 'Esa reserva ya estaba cancelada.',
  'That time is not the start of a slot of this court':
    'Esa hora no es el inicio de una franja de esta cancha.',
  'That slot has already started': 'Esa franja ya empezó.',
  'That slot is blocked for maintenance': 'Esa franja está bloqueada por mantenimiento.',
  'Incorrect email or password': 'Correo o contraseña incorrectos.',
  'Email already registered': 'Ese correo ya está registrado.',
  'Court not found': 'No se encontró la cancha.',
  'Reservation not found': 'No se encontró la reserva.',
  'Blackout not found': 'No se encontró el bloqueo.',
  'Not authenticated': 'Tu sesión terminó. Entra de nuevo.',
}

const PATTERNS: [RegExp, (m: RegExpMatchArray) => string][] = [
  [
    /^You already have the maximum of (\d+) active reservations$/,
    (m) => `Ya tienes el máximo de ${m[1]} reservas activas.`,
  ],
  [
    /^Reservations cannot be cancelled less than (\d+) hours ahead$/,
    (m) => `Las reservas no se pueden cancelar con menos de ${m[1]} horas de anticipación.`,
  ],
]

export function translateDetail(detail: string): string {
  if (detail in EXACT) return EXACT[detail]
  for (const [pattern, build] of PATTERNS) {
    const match = detail.match(pattern)
    if (match) return build(match)
  }
  return GENERIC
}

/** Error bodies are `{detail: string}`, or a list of validation errors on 422. */
export function errorMessage(error: unknown): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail
  if (typeof detail === 'string') return translateDetail(detail)
  if (Array.isArray(detail) && detail.length > 0) return 'Revisa los datos del formulario.'
  return GENERIC
}
