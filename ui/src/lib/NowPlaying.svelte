<script>
  import { player, commands } from "./store.js";
  import { fmtTime } from "./format.js";

  $: track = $player.track;
  $: duration = track ? track.duration_ms : 0;
  $: progress = duration ? Math.min($player.position_ms / duration, 1) : 0;
  $: isPlaying = $player.state === "playing";

  // Seek by tapping anywhere on the progress track.
  function seekFromEvent(e) {
    if (!duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    commands.seek(ratio * duration);
  }
</script>

<div class="np">
  <div class="art" class:placeholder={!track?.artwork_url}>
    {#if track?.artwork_url}
      <img src={track.artwork_url} alt="" />
    {:else}
      <span class="note">♪</span>
    {/if}
  </div>

  <div class="meta">
    <div class="title">{track ? track.title : "Nothing playing"}</div>
    <div class="artist">{track ? track.artist : ""}</div>
    <div class="album">{track ? track.album : ""}</div>

    <button type="button" class="bar" aria-label="Seek" on:click={seekFromEvent}>
      <div class="fill" style="width: {progress * 100}%"></div>
    </button>
    <div class="times">
      <span>{fmtTime($player.position_ms)}</span>
      <span>{fmtTime(duration)}</span>
    </div>

    <div class="transport">
      <button class="t" on:click={commands.previous} aria-label="Previous">⏮</button>
      <button class="t play" on:click={() => (isPlaying ? commands.pause() : commands.play())}>
        {isPlaying ? "⏸" : "▶"}
      </button>
      <button class="t" on:click={commands.next} aria-label="Next">⏭</button>
    </div>

    <div class="volume">
      <span class="vlabel">VOL</span>
      <input
        type="range"
        min="0"
        max="100"
        value={$player.volume}
        on:input={(e) => commands.setVolume(+e.target.value)}
      />
      <span class="vval">{$player.volume}</span>
    </div>
  </div>
</div>

<style>
  .np {
    display: grid;
    grid-template-columns: 380px 1fr;
    gap: 48px;
    padding: 48px;
    height: 100%;
    align-items: center;
  }
  .art {
    width: 380px;
    height: 380px;
    border-radius: 16px;
    overflow: hidden;
    background: var(--surface);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
    display: grid;
    place-items: center;
  }
  .art img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .placeholder .note {
    font-size: 96px;
    color: var(--muted);
  }
  .meta {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
  }
  .title {
    font-size: 36px;
    font-weight: 700;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .artist {
    font-size: 22px;
    color: var(--text);
  }
  .album {
    font-size: 16px;
    color: var(--muted);
    margin-bottom: 12px;
  }
  .bar {
    display: block;
    width: 100%;
    padding: 0;
    height: 10px;
    border-radius: 6px;
    background: var(--surface);
    overflow: hidden;
  }
  .fill {
    height: 100%;
    background: var(--accent);
  }
  .times {
    display: flex;
    justify-content: space-between;
    font-size: 14px;
    color: var(--muted);
    margin-top: 4px;
  }
  .transport {
    display: flex;
    align-items: center;
    gap: 28px;
    margin-top: 14px;
  }
  .t {
    font-size: 30px;
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: var(--surface);
    display: grid;
    place-items: center;
  }
  .t.play {
    width: 80px;
    height: 80px;
    font-size: 36px;
    background: var(--accent);
    color: #04210f;
  }
  .t:active {
    transform: scale(0.94);
  }
  .volume {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 18px;
  }
  .vlabel {
    font-size: 13px;
    color: var(--muted);
    letter-spacing: 1px;
  }
  .vval {
    font-size: 14px;
    color: var(--muted);
    width: 28px;
    text-align: right;
  }
  input[type="range"] {
    flex: 1;
    height: 28px;
    accent-color: var(--accent);
  }
</style>
