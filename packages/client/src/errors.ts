export type NeuralStockErrorCode =
  | "FETCH_FAILED"
  | "INVALID_DISCOVERY"
  | "INVALID_REGISTRY"
  | "INVALID_ASSET"
  | "ASSET_NOT_FOUND"
  | "VERSION_NOT_FOUND"
  | "ARTIFACT_NOT_FOUND"
  | "INTEGRITY_MISMATCH"
  | "INTEGRITY_UNAVAILABLE";

export class NeuralStockError extends Error {
  readonly code: NeuralStockErrorCode;

  constructor(
    code: NeuralStockErrorCode,
    message: string,
    options?: ErrorOptions,
  ) {
    super(message, options);
    this.name = "NeuralStockError";
    this.code = code;
  }
}
