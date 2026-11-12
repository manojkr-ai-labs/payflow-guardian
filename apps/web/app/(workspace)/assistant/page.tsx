import { Suspense } from "react";

import { AssistantView } from "./assistant-view";

export default function AssistantPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted">Loading assistant</p>}>
      <AssistantView />
    </Suspense>
  );
}
