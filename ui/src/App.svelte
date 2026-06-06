<script>
  import { onMount } from "svelte";
  import { connect, connected, unit } from "./lib/store.js";
  import NowPlaying from "./lib/NowPlaying.svelte";

  onMount(connect);
</script>

<main>
  <header>
    <span class="room">{$unit ? $unit.room : "HomeControl"}</span>
    <span class="status" class:online={$connected}>
      {$connected ? "●" : "○"}
    </span>
  </header>

  <NowPlaying />

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
  .status {
    color: #d9534f;
    font-size: 14px;
  }
  .status.online {
    color: var(--accent);
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
