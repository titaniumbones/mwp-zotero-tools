# Zotero HTTP API Reference

Direct HTTP endpoints for Zotero collection management. Base URL: `http://127.0.0.1:{PORT}/export-org`

Default port: 23119 (dev mode: 23124)

## Endpoints

### List Libraries

```bash
curl http://127.0.0.1:23119/export-org/libraries
```

Response:
```json
{"success": true, "libraries": [{"id": 1, "name": "My Library", "type": "user"}, ...]}
```

### List Collections (Hierarchical)

```bash
curl http://127.0.0.1:23119/export-org/collections/list
```

Response includes nested `children` arrays for subcollections.

### Get Current Collection

```bash
curl http://127.0.0.1:23119/export-org/collection/current
```

Response:
```json
{"libraryID": 1, "libraryName": "My Library", "collection": {"key": "ABC123", "name": "Papers"}}
```

### Select Collection

```bash
curl -X POST http://127.0.0.1:23119/export-org/collection/select \
  -H "Content-Type: application/json" \
  -d '{"libraryID": 1, "collectionKey": "ABC123"}'
```

Use `"collectionKey": null` to select library root.

### Create Collection

```bash
curl -X POST http://127.0.0.1:23119/export-org/collection/create \
  -H "Content-Type: application/json" \
  -d '{"libraryID": 1, "name": "New Collection"}'
```

For subcollection:
```bash
curl -X POST http://127.0.0.1:23119/export-org/collection/create \
  -H "Content-Type: application/json" \
  -d '{"libraryID": 1, "name": "Subcollection", "parentKey": "ABC123"}'
```

Response:
```json
{"success": true, "collection": {"key": "XYZ789", "name": "New Collection", "libraryID": 1, "parentKey": null}}
```

## Error Responses

All endpoints return JSON with `success: false` and `error` message on failure:

```json
{"success": false, "error": "Missing 'libraryID' parameter"}
```

HTTP status codes: 400 (bad request), 404 (not found), 500 (server error)

## Connection Check

```bash
curl http://127.0.0.1:23119/connector/ping
# Returns: Zotero is running
```
