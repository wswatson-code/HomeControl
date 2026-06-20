<script>
  import { createEventDispatcher, onMount } from "svelte";
  import { commands } from "./store.js";
  import Tile from "./Tile.svelte";
  import Keyboard from "./Keyboard.svelte";
  import DevicePicker from "./DevicePicker.svelte";

  const dispatch = createEventDispatcher();

  let tab = "playlists"; // playlists | albums | search
  let rootKind = "playlists";
  let rootItems = []; // grid for the playlists/albums tabs
  let rootTotal = 0;
  let stack = []; // drill-down pages on top of a tab (tracks / artist)
  let query = "";
  let searchResults = null;
  let searchTotals = null;
  let searchOffset = 0;
  let showDevices = false;
  let loading = false;
  let error = "";

  $: page = stack[stack.length - 1] || null;
  $: rootHasMore = rootItems.length < rootTotal;
  $: tracksHasMore = page?.kind === "tracks" && page.tracks.length < page.total;
  $: searchHasMore =
    !!searchTotals &&
    ["playlists", "albums", "artists", "tracks"].some((k) => (searchResults?.[k]?.length ?? 0) < (searchTotals[k] ?? 0));

  async function guard(fn, ...args) {
    loading = true;
    error = "";
    try {
      return await fn(...args);
    } catch (e) {
      error = String(e);
      return {};
    } finally {
      loading = false;
    }
  }

  async function loadTab(t) {
    tab = t;
    stack = [];
    searchResults = null;
    searchTotals = null;
    error = "";
    if (t === "search") return;
    rootKind = t;
    rootItems = [];
    rootTotal = 0;
    const r = await guard(t === "playlists" ? commands.getPlaylists : commands.getAlbums, 0);
    rootItems = r.items ?? [];
    rootTotal = r.total ?? 0;
  }

  async function loadMoreRoot() {
    const fn = rootKind === "playlists" ? commands.getPlaylists : commands.getAlbums;
    const r = await guard(fn, rootItems.length);
    rootItems = [...rootItems, ...(r.items ?? [])];
    rootTotal = r.total ?? rootTotal;
  }

  onMount(() => loadTab("playlists"));

  async function openItem(item) {
    if (item.type === "playlist" || item.type === "album") {
      const fn = item.type === "playlist" ? commands.getPlaylistTracks : commands.getAlbumTracks;
      const r = await guard(fn, item.id, 0);
      stack = [
        ...stack,
        {
          kind: "tracks",
          id: item.id,
          ctype: item.type,
          title: item.name,
          context_uri: item.uri,
          tracks: r.tracks ?? [],
          total: r.total ?? 0,
        },
      ];
    } else if (item.type === "artist") {
      const a = await guard(commands.getArtist, item.id);
      stack = [...stack, { kind: "artist", title: item.name, top: a.top_tracks ?? [], albums: a.albums ?? [] }];
    } else if (item.type === "track") {
      commands.playContent({ uris: [item.uri] });
    }
  }

  async function loadMoreTracks() {
    const p = stack[stack.length - 1];
    const fn = p.ctype === "playlist" ? commands.getPlaylistTracks : commands.getAlbumTracks;
    const r = await guard(fn, p.id, p.tracks.length);
    const updated = { ...p, tracks: [...p.tracks, ...(r.tracks ?? [])], total: r.total ?? p.total };
    stack = [...stack.slice(0, -1), updated];
  }

  const back = () => (stack = stack.slice(0, -1));
  const playContext = (uri, offset = null) => commands.playContent({ context_uri: uri, offset });
  const playTrackId = (id) => commands.playContent({ uris: [`spotify:track:${id}`] });

  async function runSearch() {
    if (!query.trim()) return;
    const r = await guard(commands.search, query.trim(), 0);
    searchResults = r;
    searchTotals = r.totals ?? {};
    searchOffset = r.limit ?? 20;
  }

  async function loadMoreSearch() {
    const r = await guard(commands.search, query.trim(), searchOffset);
    const merged = { ...searchResults };
    for (const k of ["playlists", "albums", "artists", "tracks"]) {
      if (r[k]?.length) merged[k] = [...(searchResults[k] ?? []), ...r[k]];
    }
    searchResults = merged;
    searchTotals = r.totals ?? searchTotals;
    searchOffset += r.limit ?? 20;
  }
</script>

<div class="browse">
  <header>
    <button class="nav" on:click={() => (page ? back() : dispatch("close"))}>
      {page ? "‹ Back" : "✕ Close"}
    </button>
    {#if page}
      <span class="ptitle">{page.title}</span>
    {:else}
      <div class="tabs">
        <button class:active={tab === "playlists"} on:click={() => loadTab("playlists")}>Playlists</button>
        <button class:active={tab === "albums"} on:click={() => loadTab("albums")}>Albums</button>
        <button class:active={tab === "search"} on:click={() => loadTab("search")}>Search</button>
      </div>
    {/if}
    <button class="devbtn" on:click={() => (showDevices = true)}>🔈 Device</button>
  </header>

  {#if error}<div class="error">{error}</div>{/if}

  <div class="content">
    {#if page?.kind === "tracks"}
      <button class="playall" on:click={() => playContext(page.context_uri)}>▶ Play all</button>
      {#each page.tracks as t, i}
        <button class="track" on:click={() => playContext(page.context_uri, i)}>
          <span class="tn">{i + 1}</span>
          <span class="tt">{t.title}</span>
          <span class="ta">{t.artist}</span>
        </button>
      {/each}
      {#if tracksHasMore}<button class="more" on:click={loadMoreTracks}>Load more</button>{/if}
    {:else if page?.kind === "artist"}
      <h4>Top tracks</h4>
      {#each page.top as t}
        <button class="track" on:click={() => playTrackId(t.id)}>
          <span class="tt">{t.title}</span>
          <span class="ta">{t.artist}</span>
        </button>
      {/each}
      {#if page.albums.length}
        <h4>Albums</h4>
        <div class="grid">
          {#each page.albums as a}<Tile item={a} on:open={() => openItem(a)} />{/each}
        </div>
      {/if}
    {:else if tab === "search"}
      <div class="searchbar">{query || "Type to search…"}</div>
      <Keyboard
        on:key={(e) => (query += e.detail)}
        on:space={() => (query += " ")}
        on:backspace={() => (query = query.slice(0, -1))}
        on:submit={runSearch}
      />
      {#if searchResults}
        {#each ["playlists", "albums", "artists", "tracks"] as sec}
          {#if searchResults[sec]?.length}
            <h4>{sec}</h4>
            {#if sec === "tracks"}
              {#each searchResults[sec] as t}
                <button class="track" on:click={() => commands.playContent({ uris: [t.uri] })}>
                  <span class="tt">{t.name}</span>
                  <span class="ta">{t.subtitle}</span>
                </button>
              {/each}
            {:else}
              <div class="grid">
                {#each searchResults[sec] as it}<Tile item={it} on:open={() => openItem(it)} />{/each}
              </div>
            {/if}
          {/if}
        {/each}
        {#if searchHasMore}<button class="more" on:click={loadMoreSearch}>Load more</button>{/if}
      {/if}
    {:else}
      <div class="grid">
        {#each rootItems as it}<Tile item={it} on:open={() => openItem(it)} />{/each}
      </div>
      {#if rootHasMore}<button class="more" on:click={loadMoreRoot}>Load more</button>{/if}
    {/if}

    {#if loading}<div class="loading">Loading…</div>{/if}
  </div>
</div>

{#if showDevices}<DevicePicker on:close={() => (showDevices = false)} />{/if}

<style>
  .browse {
    position: absolute;
    inset: 0;
    background: var(--bg, #121212);
    display: flex;
    flex-direction: column;
    z-index: 20;
  }
  header {
    flex: 0 0 56px;
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 0 16px;
    border-bottom: 1px solid var(--surface);
  }
  .nav,
  .devbtn {
    background: var(--surface);
    border: none;
    color: var(--text);
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 16px;
    cursor: pointer;
  }
  .devbtn {
    margin-left: auto;
  }
  .ptitle {
    font-size: 18px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .tabs {
    display: flex;
    gap: 8px;
  }
  .tabs button {
    background: none;
    border: none;
    color: var(--muted);
    font-size: 17px;
    padding: 8px 10px;
    cursor: pointer;
    border-bottom: 2px solid transparent;
  }
  .tabs button.active {
    color: var(--text);
    border-bottom-color: var(--accent);
  }
  .content {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
  }
  .grid {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
  }
  h4 {
    text-transform: capitalize;
    color: var(--muted);
    margin: 16px 0 8px;
  }
  .track {
    display: flex;
    align-items: center;
    gap: 14px;
    width: 100%;
    background: none;
    border: none;
    color: var(--text);
    padding: 12px 8px;
    font-size: 17px;
    text-align: left;
    border-bottom: 1px solid var(--surface);
    cursor: pointer;
  }
  .tn {
    color: var(--muted);
    width: 28px;
    text-align: right;
  }
  .tt {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ta {
    color: var(--muted);
    font-size: 15px;
    max-width: 40%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .playall {
    background: var(--accent);
    color: #04210f;
    border: none;
    border-radius: 10px;
    padding: 12px 18px;
    font-size: 17px;
    margin-bottom: 12px;
    cursor: pointer;
  }
  .more {
    display: block;
    margin: 16px auto;
    background: var(--surface);
    color: var(--text);
    border: none;
    border-radius: 10px;
    padding: 12px 28px;
    font-size: 16px;
    cursor: pointer;
  }
  .searchbar {
    background: var(--surface);
    color: var(--text);
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 18px;
    min-height: 24px;
  }
  .error {
    background: #d9534f;
    color: #fff;
    padding: 8px 16px;
    font-size: 14px;
  }
  .loading {
    color: var(--muted);
    padding: 8px 16px;
  }
</style>
