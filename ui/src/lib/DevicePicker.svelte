<script>
  import { createEventDispatcher, onMount } from "svelte";
  import { commands, targetDevice } from "./store.js";
  const dispatch = createEventDispatcher();

  let devices = [];
  let loading = true;
  let error = "";

  onMount(async () => {
    try {
      devices = (await commands.getDevices()).devices ?? [];
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
    }
  });

  function pick(d) {
    // Just remember the target; the next play sends device_id explicitly (no transfer call,
    // which would 404 when nothing is playing yet).
    targetDevice.set(d.id);
    dispatch("close");
  }
</script>

<div class="backdrop" role="presentation" on:click|self={() => dispatch("close")}>
  <div class="panel" role="dialog" aria-label="Choose playback device">
    <h3>Play on…</h3>
    {#if loading}
      <p class="muted">Loading devices…</p>
    {:else if error}
      <p class="muted">Couldn't load devices: {error}</p>
    {:else if !devices.length}
      <p class="muted">No devices found — make sure this unit's librespot is running and on the same network.</p>
    {:else}
      {#each devices as d}
        <button class="dev" class:active={$targetDevice === d.id || (!$targetDevice && d.is_active)} on:click={() => pick(d)}>
          <span class="dn">{d.name}</span>
          <span class="dt">{d.type}</span>
        </button>
      {/each}
    {/if}
    <button class="cancel" on:click={() => dispatch("close")}>Cancel</button>
  </div>
</div>

<style>
  .backdrop {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: grid;
    place-items: center;
    z-index: 30;
  }
  .panel {
    width: 420px;
    max-height: 80%;
    overflow-y: auto;
    background: #1b1b1b;
    border-radius: 14px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  h3 {
    margin: 0 0 8px;
    color: var(--text);
  }
  .muted {
    color: var(--muted);
  }
  .dev {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 16px;
    border: none;
    border-radius: 10px;
    background: var(--surface);
    color: var(--text);
    font-size: 18px;
    cursor: pointer;
  }
  .dev.active {
    outline: 2px solid var(--accent);
  }
  .dt {
    color: var(--muted);
    font-size: 14px;
  }
  .cancel {
    margin-top: 8px;
    padding: 12px;
    border: none;
    border-radius: 10px;
    background: var(--surface);
    color: var(--muted);
    cursor: pointer;
  }
</style>
