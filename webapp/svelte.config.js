import adapter from "@sveltejs/adapter-static";

/** @type {import('@sveltejs/kit').Config} */
export default {
  kit: {
    // Static site: single prerendered page, client-side state for screens.
    adapter: adapter({ fallback: "index.html" }),
  },
};
