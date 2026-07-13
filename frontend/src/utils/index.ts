/**
 * Cookie helpers (backed by js-cookie).
 * Only the helpers actually used by the LLM Gate frontend are exported here.
 */
import Cookies from 'js-cookie';

export function getCookieForKey(key: string): string | undefined {
    return Cookies.get(key);
}

export function setCookie(key: string, value: string, params?: Cookies.CookieAttributes): void {
    Cookies.set(key, value, params);
}

export function removeCookieForKey(key: string): void {
    Cookies.remove(key);
}
