/* TEGAD — service worker (gerado pelo servidor; versão muda a cada atualização da aplicação) */
const VERSAO = {{ versao|tojson }};
const CACHE_ESTATICO = "tegad-estatico-" + VERSAO;
const CACHE_PAGINAS = "tegad-paginas-" + VERSAO;
const PRECACHE = {{ precache|tojson }};
const OFFLINE = {{ offline|tojson }};
// páginas somente leitura que podem ser abertas da memória quando a conexão cair
const PAGINAS_CACHEAVEIS = ["/consulta/"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_ESTATICO)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())  // nova versão assume sem esperar fechar as abas
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((chaves) => Promise.all(
        chaves.filter((k) => k.startsWith("tegad-") && !k.endsWith(VERSAO)).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;               // formulários sempre vão ao servidor
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // arquivos estáticos versionados: cache primeiro
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((resp) => {
        if (resp.ok) {
          const copia = resp.clone();
          caches.open(CACHE_ESTATICO).then((c) => c.put(req, copia));
        }
        return resp;
      }))
    );
    return;
  }

  // páginas: rede primeiro; sem conexão, usa a cópia salva (só consulta) ou a página offline
  if (req.mode === "navigate") {
    const cacheavel = PAGINAS_CACHEAVEIS.some((p) => url.pathname.startsWith(p));
    event.respondWith(
      fetch(req).then((resp) => {
        if (cacheavel && resp.ok) {
          const copia = resp.clone();
          caches.open(CACHE_PAGINAS).then((c) => c.put(req, copia));
        }
        return resp;
      }).catch(() => caches.match(req).then((hit) => hit || caches.match(OFFLINE)))
    );
  }
});

self.addEventListener("message", (event) => {
  if (event.data === "limpar-paginas") caches.delete(CACHE_PAGINAS);  // ao sair do sistema
});
