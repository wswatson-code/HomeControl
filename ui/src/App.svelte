<script>
  import { onMount } from "svelte";
  import { connect, connected, unit, player, commands } from "./lib/store.js";
  import { initAlarmAudio } from "./lib/alarm.js";
  import NowPlaying from "./lib/NowPlaying.svelte";
  import Timers from "./lib/Timers.svelte";
  import VoiceOverlay from "./lib/VoiceOverlay.svelte";
  import Browse from "./lib/Browse.svelte";

  let showBrowse = false;

  // On first snapshot ($unit becomes set), if nothing is loaded, open Browse so a freshly
  // booted unit lands on something useful instead of an empty now-playing. One-shot — it
  // won't reopen every time playback later stops.
  let didStartupCheck = false;
  $: if (!didStartupCheck && $unit) {
    didStartupCheck = true;
    if (!$player.track) showBrowse = true;
  }

  onMount(() => {
    connect();
    initAlarmAudio();
  });
</script>

<main>
  <header>
    <span class="room">{$unit ? $unit.room : "HomeControl"}</span>
    <span class="header-right">
      <button class="browse-btn" on:click={() => (showBrowse = true)}>Browse</button>
      <span class="status" class:online={$connected}>
        {$connected ? "●" : "○"}
      </span>
      <button class="exit" on:click={commands.stopKiosk} aria-label="Exit kiosk" title="Exit kiosk">⏻</button>
    </span>
  </header>

  <NowPlaying />

  <Timers />
  <VoiceOverlay />

  {#if showBrowse}
    <Browse on:close={() => (showBrowse = false)} />
  {/if}

  {#if !$connected}
    <div class="offline">Reconnecting…</div>
  {/if}
</main>

<style>
  main {
    width: 1024px;
    height: 600px;
    position: relative;
    display: flex;
    flex-direction: column;
  }
  header {
    height: 44px;
    flex: 0 0 44px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    color: var(--muted);
    font-size: 16px;
    letter-spacing: 0.5px;
  }
  .header-right {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  .status {
    color: #d9534f;
    font-size: 14px;
  }
  .status.online {
    color: var(--accent);
  }
  .browse-btn {
    background: var(--surface);
    border: none;
    color: var(--text);
    font-size: 15px;
    padding: 6px 14px;
    border-radius: 8px;
    cursor: pointer;
  }
  .exit {
    background: none;
    border: none;
    color: var(--muted);
    font-size: 18px;
    line-height: 1;
    padding: 6px 8px;
    border-radius: 6px;
    cursor: pointer;
  }
  .exit:active {
    color: #d9534f;
    background: rgba(255, 255, 255, 0.06);
  }
  .offline {
    position: absolute;
    bottom: 16px;
    left: 0;
    right: 0;
    text-align: center;
    color: var(--muted);
    font-size: 14px;
  }
</style>
