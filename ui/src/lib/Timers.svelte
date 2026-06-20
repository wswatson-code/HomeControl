<script>
  import { onMount, onDestroy } from "svelte";
  import { timers, commands } from "./store.js";
  import { fmtTime } from "./format.js";
  import { startAlarm, stopAlarm } from "./alarm.js";

  // Local clock so each timer counts down smoothly between server ticks (the server only
  // pushes on create/fire/dismiss; remaining time is derived from fires_at_ms locally).
  let now = Date.now();
  const tick = setInterval(() => (now = Date.now()), 250);
  onMount(() => (now = Date.now()));
  onDestroy(() => {
    clearInterval(tick);
    stopAlarm();
  });

  const remaining = (t) => Math.max(0, t.fires_at_ms - now);

  // Ring while any timer is fired; silence when the last one is dismissed.
  $: if ($timers.some((t) => t.state === "fired")) startAlarm();
  else stopAlarm();
</script>

{#if $timers.length}
  <div class="timers">
    {#each $timers as t (t.id)}
      <div class="timer" class:fired={t.state === "fired"}>
        <span class="label">{t.label || "Timer"}</span>
        <span class="time">{t.state === "fired" ? "Time's up" : fmtTime(remaining(t))}</span>
        <button class="dismiss" on:click={() => commands.dismissTimer(t.id)} aria-label="Dismiss timer">✕</button>
      </div>
    {/each}
  </div>
{/if}

<style>
  .timers {
    position: absolute;
    bottom: 16px;
    right: 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    align-items: flex-end;
  }
  .timer {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
    border-radius: 10px;
    background: var(--surface);
    color: var(--text);
    font-size: 18px;
  }
  .timer.fired {
    background: #d9534f;
    color: #fff;
    animation: pulse 0.8s ease-in-out infinite;
  }
  .label {
    color: var(--muted);
  }
  .timer.fired .label {
    color: #fff;
  }
  .time {
    font-variant-numeric: tabular-nums;
    font-weight: 700;
  }
  .dismiss {
    background: none;
    border: none;
    color: inherit;
    font-size: 16px;
    padding: 2px 6px;
    cursor: pointer;
  }
  @keyframes pulse {
    50% {
      opacity: 0.55;
    }
  }
</style>
