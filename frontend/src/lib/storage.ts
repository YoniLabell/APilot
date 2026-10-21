// Browser storage can be unavailable (private mode, blocked site data); never let it break the app.

export function readJSON<T>(storage: () => Storage, key: string, fallback: T): T {
  try {
    const value = storage().getItem(key)
    return value ? (JSON.parse(value) as T) : fallback
  } catch {
    return fallback
  }
}

export function readText(storage: () => Storage, key: string) {
  try {
    return storage().getItem(key) ?? ''
  } catch {
    return ''
  }
}

export function write(storage: () => Storage, key: string, value: string) {
  try {
    storage().setItem(key, value)
    return true
  } catch {
    return false
  }
}

export const local = () => window.localStorage
export const session = () => window.sessionStorage
