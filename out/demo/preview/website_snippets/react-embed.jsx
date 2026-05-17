import React from "react";
import { createMotionJSONTemplateEmbeds } from "@motionjson/runtime/react";

const { HeroMotionJSON, EcommerceMotionJSON, EducationMotionJSON } = createMotionJSONTemplateEmbeds(React);

export function ProductHeroMotion() {
  return (
    <HeroMotionJSON
      source="/motionjson/web_asset_manifest.json"
      style={{ width: "100%", aspectRatio: "16 / 10" }}
      options={{ background: "#fbfaf6" }}
    />
  );
}

export function ProductTileMotion() {
  return (
    <EcommerceMotionJSON
      source="/motionjson/web_asset_manifest.json"
      style={{ width: "100%", aspectRatio: "1 / 1" }}
      options={{ background: "#ffffff", scrollState: false }}
    />
  );
}

export function LessonMotion() {
  return (
    <EducationMotionJSON
      source="/motionjson/web_asset_manifest.json"
      style={{ width: "100%", aspectRatio: "16 / 9" }}
      options={{ background: "#f4f7fb" }}
    />
  );
}
