export function pageError(details) {
  // CDP's text is often only "Uncaught"; the actual Error is in exception.description.
  const description = details?.exception?.description || details?.exception?.value;
  const message = typeof description === "string" ? description.split("\n")[0] : details?.text;
  return (message || "Page inspection failed").replace(/^Error:\s*/, "");
}
