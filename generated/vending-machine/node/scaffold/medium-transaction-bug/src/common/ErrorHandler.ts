export function handleError(error: Error) {
  console.error(error);
  return { error: error.message };
}