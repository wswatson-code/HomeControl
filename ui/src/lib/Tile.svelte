<script>
  import { createEventDispatcher } from "svelte";
  export let item;
  const dispatch = createEventDispatcher();
</script>

<button class="tile" on:click={() => dispatch("open")}>
  <div class="art" class:ph={!item.image}>
    {#if item.image}<img src={item.image} alt="" />{:else}<span>♪</span>{/if}
  </div>
  <div class="name">{item.name}</div>
  {#if item.subtitle}<div class="sub">{item.subtitle}</div>{/if}
</button>

<style>
  .tile {
    width: 150px;
    background: none;
    border: none;
    padding: 0;
    text-align: left;
    color: var(--text);
    cursor: pointer;
  }
  .art {
    width: 150px;
    height: 150px;
    border-radius: 10px;
    overflow: hidden;
    background: var(--surface);
    display: grid;
    place-items: center;
  }
  .art img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .ph span {
    font-size: 48px;
    color: var(--muted);
  }
  .name {
    margin-top: 6px;
    font-size: 15px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .sub {
    font-size: 13px;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .tile:active {
    transform: scale(0.97);
  }
</style>
