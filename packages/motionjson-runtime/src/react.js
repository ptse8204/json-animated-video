import { mountMotionJSON } from "./embed.js";

export function createMotionJSONReactComponent(React, mount = mountMotionJSON) {
  if (!React?.useEffect || !React?.useRef) {
    throw new Error("Pass a React instance to createMotionJSONReactComponent");
  }
  return function MotionJSONPlayer({ source, manifest, renderer = "canvas", options = {}, className = "", style = null, onReady = null }) {
    const ref = React.useRef(null);
    React.useEffect(() => {
      let mounted = true;
      let handle = null;
      mount(ref.current, source || manifest, { ...options, renderer }).then((runtimeHandle) => {
        if (!mounted) {
          runtimeHandle.destroy();
          return;
        }
        handle = runtimeHandle;
        onReady?.(runtimeHandle);
      });
      return () => {
        mounted = false;
        handle?.destroy();
      };
    }, [source, manifest, renderer]);
    return React.createElement("div", { ref, className, style });
  };
}
