<script>
  import { createEventDispatcher, onMount } from "svelte";
  import { commands } from "./store.js";
  import Tile from "./Tile.svelte";
  import Keyboard from "./Keyboard.svelte";
  import DevicePicker from "./DevicePicker.svelte";

  const dispatch = createEventDispatcher();

  let tab = "playlists"; // playlists | albums | search
  let rootItems = []; // grid for the playlists/albums tabs
  let stack = []; // drill-down pages on top of a tab (tracks / artist)
  let query = "";
  let searchResults = null;
  let showDevices = false;
  let loading = false;
  let error = "";

  $: page = stack[stack.length - 1] || null;

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
    error = "";
    if (t === "playlists") rootItems = (await guard(commands.getPlaylists)).items ?? [];
    else if (t === "albums") rootItems = (await guard(commands.getAlbums)).items ?? [];
  }

  onMount(() => loadTab("playlists"));

  async function openItem(item) {
    if (item.type === "playlist") {
      const { tracks } = await guard(commands.getPlaylistTracks, item.id);
      stack = [...stack, { kind: "tracks", title: item.name, context_uri: item.uri, tracks: tracks ?? [] }];
    } else if (item.type === "album") {
      const { tracks } = await guard(commands.getAlbumTracks, item.id);
      stack = [...stack, { kind: "tracks", title: item.name, context_uri: item.uri, tracks: tracks ?? [] }];
    } else if (item.type === "artist") {
      const a = await guard(commands.getArtist, item.id);
      stack = [...stack, { kind: "artist", title: item.name, top: a.top_tracks ?? [], albums: a.albums ?? [] }];
    } else if (item.type === "track") {
      commands.playContent({ uris: [item.uri] });
    }
  }

  const back = () => (stack = stack.slice(0, -1));
  const playContext = (uri, offset = null) => commands.playContent({ context_uri: uri, offset });
  const playTrackId = (id) => commands.playContent({ uris: [`spotify:track:${id}`] });

  const runSearch = async () => {
    if (query.trim()) searchResults = await guard(commands.search, query.trim());
  };
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
        <button class:active={tab === "search"} on:click={() => { tab = "search"; stack = []; }}>Search</button>
      </div>
    {/if}
    <button class="devbtn" on:click={() => (showDevices = true)}>🔈 Device</button>
  </header>

  {#if error}<div class="error">{error}</div>{/if}
  {#if loading}<div class="loading">Loading…</div>{/if}

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
      {/if}
    {:else}
      <div class="grid">
        {#each rootItems as it}<Tile item={it} on:open={() => openItem(it)} />{/each}
      </div>
    {/if}
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
