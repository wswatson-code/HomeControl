<script>
  import { voice } from "./store.js";

  // Shown only while the pipeline is active (anything but idle).
  $: active = $voice.phase && $voice.phase !== "idle";

  // Reactive so the spoken reply updates live when phase === "speaking".
  $: heading =
    $voice.phase === "listening"
      ? "Listening…"
      : $voice.phase === "thinking"
        ? "Thinking…"
        : $voice.phase === "speaking"
          ? $voice.reply || ""
          : "";
</script>

{#if active}
  <div class="overlay" class:listening={$voice.phase === "listening"}>
    <div class="dot"></div>
    <div class="text">
      <div class="heading">{heading}</div>
      {#if $voice.transcript}
        <div class="transcript">"{$voice.transcript}"</div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .overlay {
    position: absolute;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 16px 28px;
    border-radius: 16px;
    background: rgba(0, 0, 0, 0.72);
    backdrop-filter: blur(6px);
    max-width: 80%;
  }
  .dot {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--accent);
    flex: 0 0 auto;
  }
  .listening .dot {
    animation: pulse 1s ease-in-out infinite;
  }
  .heading {
    font-size: 22px;
    font-weight: 600;
    color: var(--text);
  }
  .transcript {
    font-size: 16px;
    color: var(--muted);
    margin-top: 2px;
  }
  @keyframes pulse {
    0%,
    100% {
      transform: scale(1);
      opacity: 1;
    }
    50% {
      transform: scale(1.5);
      opacity: 0.5;
    }
  }
</style>
