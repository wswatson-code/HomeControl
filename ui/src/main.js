import "./app.css";
import { mount } from "svelte";
import App from "./App.svelte";

// Svelte 5: mount() establishes the effect root. (The legacy `new App({target})` API
// does not, which orphans child-component effects — e.g. the `$:` blocks in NowPlaying.)
const app = mount(App, { target: document.getElementById("app") });

export default app;
