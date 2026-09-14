# Versioning Spec
- Behavior-affecting change (code/threshold/param/prompt/template/config/runtime option) =>
  NEW immutable policy_id (e.g. black-b3-v1 -> black-b3-v2). Never mutate a sealed policy.
- Metadata-only (description/notes/evaluation_role) => in-place update allowed.
- Sealed: artifact/config/prompt/environment sealed; drift => ARTIFACT_DRIFT reported, never
  silently rehashed.
- Aliases: legacy strategy ids (black-b3) may point to the active immutable version; version
  rows themselves never change.
- Lineage: parent_policy_id recorded (B1<-B0, B2<-B1, B3<-B2); future black-auto-* can parent
  to any frozen version.
