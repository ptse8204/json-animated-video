import { mountMotionJSON } from "./embed.js";
import { getMotionJSONTemplate } from "./templates.js";

export function createMotionJSONReactComponent(React, mount = mountMotionJSON) {
  if (!React?.useEffect || !React?.useRef) {
    throw new Error("Pass a React instance to createMotionJSONReactComponent");
  }
  return function MotionJSONPlayer({ source, manifest, renderer = "canvas", template = null, options = {}, className = "", style = null, onReady = null }) {
    const ref = React.useRef(null);
    React.useEffect(() => {
      let mounted = true;
      let handle = null;
      mount(ref.current, source || manifest, { ...options, renderer, template }).then((runtimeHandle) => {
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
    }, [source, manifest, renderer, template]);
    return React.createElement("div", { ref, className, style });
  };
}

export function createMotionJSONTemplateComponent(React, template, mount = mountMotionJSON) {
  const MotionJSONPlayer = createMotionJSONReactComponent(React, mount);
  const preset = getMotionJSONTemplate(template);
  const templateId = preset?.id || template;
  const templateClass = preset?.className || "";
  return function MotionJSONTemplatePlayer({ className = "", options = {}, ...props }) {
    const mergedClassName = [templateClass, className].filter(Boolean).join(" ");
    return React.createElement(MotionJSONPlayer, {
      ...props,
      template: templateId,
      options,
      className: mergedClassName
    });
  };
}

export function createMotionJSONTemplateEmbeds(React, mount = mountMotionJSON) {
  return {
    MotionJSONPlayer: createMotionJSONReactComponent(React, mount),
    HeroMotionJSON: createMotionJSONTemplateComponent(React, "hero", mount),
    EcommerceMotionJSON: createMotionJSONTemplateComponent(React, "ecommerce", mount),
    EducationMotionJSON: createMotionJSONTemplateComponent(React, "education", mount)
  };
}
