// Stands in for DOMPurify, which needs a DOM that Node lacks. Mermaid only
// sanitizes label text with it, which doesn't change whether a diagram parses.
export default {
  isSupported: true,
  sanitize: (text: string) => text,
  addHook() {},
  removeHook() {},
  removeAllHooks() {},
};
