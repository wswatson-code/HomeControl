<script>
  import { onMount } from "svelte";
  import { connect, connected, unit, player, showBrowse, commands } from "./lib/store.js";
  import { initAlarmAudio } from "./lib/alarm.js";
  import NowPlaying from "./lib/NowPlaying.svelte";
  import Timers from "./lib/Timers.svelte";
  import VoiceOverlay from "./lib/VoiceOverlay.svelte";
  import Browse from "./lib/Browse.svelte";

  // On first snapshot ($unit becomes set), if nothing is loaded, open Browse so a freshly
  // booted unit lands on something useful instead of an empty now-playing. One-shot — it
  // won't reopen every time playback later stops.
  let didStartupCheck = false;
  $: if (!didStartupCheck && $unit) {
    didStartupCheck = true;
    if (!$player.track) showBrowse.set(true);
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
      <button class="browse-btn" on:click={() => showBrowse.set(true)}>Browse</button>
      <span class="status" class:online={$connected}>
        {$connected ? "●" : "○"}
      </span>
      <button class="exit" on:click={commands.stopKiosk} aria-label="Exit kiosk" title="Exit kiosk">⏻</button>
    </span>
  </header>

  <NowPlaying />

  <Timers />
  <VoiceOverlay />

  {#if $showBrowse}
    <Browse on:close={() => showBrowse.set(false)} />
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
    height: 59px;
    flex: 0 0 59px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 32px;
    color: var(--muted);
    font-size: 21px;
    letter-spacing: 0.5px;
  }
  .header-right {
    display: flex;
    align-items: center;
    gap: 21px;
  }
  .browse-btn {
    background: var(--surface);
    border: none;
    color: var(--text);
    font-size: 20px;
    padding: 8px 19px;
    border-radius: 11px;
    cursor: pointer;
  }
  .browse-btn:active {
    transform: scale(0.96);
  }
  .status {
    color: #d9534f;
    font-size: 19px;
  }
  .status.online {
    color: var(--accent);
  }
  .exit {
    background: none;
    border: none;
    color: var(--muted);
    font-size: 24px;
    line-height: 1;
    padding: 8px 11px;
    border-radius: 8px;
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
