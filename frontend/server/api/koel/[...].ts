import {
  appendHeader,
  defineEventHandler,
  getMethod,
  getQuery,
  getRequestHeaders,
  getRouterParam,
  readRawBody,
  setResponseHeader,
  setResponseStatus,
} from 'h3'

const HOP_BY_HOP = new Set([
  'host',
  'connection',
  'content-length',
  'accept-encoding', // let Node/undici handle encoding end-to-end
  'transfer-encoding',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'upgrade',
])

function rewriteSetCookie(cookie: string, isDev: boolean): string {
  let out = cookie
    // cookie must attach to the dashboard origin, not the backend host
    .replace(/;\s*Domain=[^;]+/gi, '')
    // collapse path to root so the cookie is sent on every /api/koel call
    .replace(/;\s*Path=[^;]+/gi, '; Path=/')
  // http dev can't carry Secure cookies
  if (isDev) out = out.replace(/;\s*Secure/gi, '')
  return out
}


export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const base = (config.koelApiBase as string).replace(/\/+$/, '')
  const pathParam = getRouterParam(event, '_') ?? ''
  const query = getQuery(event)

  const url = new URL(`${base}/${pathParam}`)
  for (const [k, v] of Object.entries(query)) {
    if (v == null) continue
    if (Array.isArray(v)) v.forEach((x) => url.searchParams.append(k, String(x)))
    else url.searchParams.set(k, String(v))
  }

  const method = getMethod(event)
  const incoming = getRequestHeaders(event)
  const headers = new Headers()
  for (const [k, v] of Object.entries(incoming)) {
    if (!v) continue
    if (HOP_BY_HOP.has(k.toLowerCase())) continue
    headers.set(k, Array.isArray(v) ? v.join(', ') : v)
  }

  const body =
    method === 'GET' || method === 'HEAD' ? undefined : await readRawBody(event, false)

  const resp = await fetch(url.toString(), {
    method,
    headers,
    body: body as BodyInit | undefined,
    redirect: 'manual',
  })

  // Nuxt's typed dev flag (true under `nuxt dev`); avoids an untyped
  // `process` reference in the Nitro handler. http dev can't carry Secure cookies.
  const isDev = import.meta.dev === true
  const setCookies =
    typeof resp.headers.getSetCookie === 'function' ? resp.headers.getSetCookie() : []
  for (const c of setCookies) {
    appendHeader(event, 'set-cookie', rewriteSetCookie(c, isDev))
  }

  const contentType = resp.headers.get('content-type')
  if (contentType) setResponseHeader(event, 'content-type', contentType)
  const cacheControl = resp.headers.get('cache-control')
  if (cacheControl) setResponseHeader(event, 'cache-control', cacheControl)

  setResponseStatus(event, resp.status)
  return new Uint8Array(await resp.arrayBuffer())
})
