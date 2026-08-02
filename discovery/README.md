# NeuralStock machine discovery

`neuralstock.json` is the source of truth for the public discovery document at
`https://neuralstock.ai/.well-known/neuralstock.json`.

The website build must copy this file byte-for-byte to
`public/.well-known/neuralstock.json`. Serve it with
`Content-Type: application/json; charset=utf-8`,
`Access-Control-Allow-Origin: *`, and a short revalidating cache policy. Contract
changes require a schema-version review; endpoint changes must also update the
TypeScript and Python discovery constants and their tests.
