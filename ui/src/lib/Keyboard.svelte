<script>
  import { createEventDispatcher } from "svelte";
  const dispatch = createEventDispatcher();
  const rows = ["qwertyuiop", "asdfghjkl", "zxcvbnm"];
</script>

<div class="kb">
  {#each rows as row}
    <div class="row">
      {#each row.split("") as k}
        <button class="key" on:click={() => dispatch("key", k)}>{k}</button>
      {/each}
    </div>
  {/each}
  <div class="row">
    <button class="key wide" on:click={() => dispatch("space")}>space</button>
    <button class="key" on:click={() => dispatch("backspace")}>⌫</button>
    <button class="key go" on:click={() => dispatch("submit")}>search</button>
  </div>
</div>

<style>
  .kb {
    display: flex;
    flex-direction: column;
    gap: 6px;
    align-items: center;
    margin: 10px 0;
  }
  .row {
    display: flex;
    gap: 6px;
  }
  .key {
    min-width: 44px;
    height: 44px;
    border: none;
    border-radius: 8px;
    background: var(--surface);
    color: var(--text);
    font-size: 18px;
    cursor: pointer;
  }
  .key.wide {
    min-width: 220px;
  }
  .key.go {
    min-width: 90px;
    background: var(--accent);
    color: #04210f;
  }
  .key:active {
    transform: scale(0.94);
  }
</style>
