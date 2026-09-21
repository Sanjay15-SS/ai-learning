# Tool description diff - the third tool, and the overlap it removed

Before, `search_docs` and `get_openapi_spec` both claimed "documentation", "endpoints" and "details", and `api_version` was a free string. After, each tool names one job and what it does not do; `api_version` and `method` are enums; `check_deprecation` is new and overlaps neither.

```diff
--- TOOLS_TWO (before)
+++ TOOLS_THREE (after)
@@ -1,42 +1,85 @@
 [
   {
     "name": "search_docs",
-    "description": "Search the Ledgerline API documentation and specification for information about endpoints, parameters and versions.",
+    "description": "Full-text search over the prose guide pages of ONE api_version. Returns the 3 best pages (id, title, endpoints listed on the page, text). Use it to find which endpoint does a task. It does not return parameter schemas and does not report deprecations.",
     "input_schema": {
       "type": "object",
       "properties": {
         "query": {
-          "type": "string"
+          "type": "string",
+          "description": "what the developer wants to do"
         },
         "api_version": {
           "type": "string",
-          "description": "API version"
+          "enum": [
+            "v2",
+            "v3"
+          ]
         }
       },
       "required": [
         "query",
         "api_version"
-      ]
+      ],
+      "additionalProperties": false
     }
   },
   {
     "name": "get_openapi_spec",
-    "description": "Get API reference information for an endpoint, including docs and details about the API.",
+    "description": "Return the OpenAPI operation for ONE exact method + path in ONE api_version: path/query/header parameters, required body fields, deprecated flag. Needs an exact path such as /v3/refunds; it does not search and does not say what replaces a deprecated operation.",
     "input_schema": {
       "type": "object",
       "properties": {
+        "method": {
+          "type": "string",
+          "enum": [
+            "GET",
+            "POST",
+            "DELETE"
+          ]
+        },
         "path": {
+          "type": "string",
+          "description": "e.g. /v3/payment_intents/{intent_id}"
+        },
+        "api_version": {
+          "type": "string",
+          "enum": [
+            "v2",
+            "v3"
+          ]
+        }
+      },
+      "required": [
+        "method",
+        "path",
+        "api_version"
+      ],
+      "additionalProperties": false
+    }
+  },
+  {
+    "name": "check_deprecation",
+    "description": "Look up ONE symbol - an endpoint ('POST /v2/charges'), parameter ('source'), header or event name - in the v2->v3 changelog. Returns whether it is deprecated, removed or renamed in api_version and what replaces it. It returns no docs text and no schema.",
+    "input_schema": {
+      "type": "object",
+      "properties": {
+        "symbol": {
           "type": "string"
         },
         "api_version": {
           "type": "string",
-          "description": "API version"
+          "enum": [
+            "v2",
+            "v3"
+          ]
         }
       },
       "required": [
-        "path",
+        "symbol",
         "api_version"
-      ]
+      ],
+      "additionalProperties": false
     }
   }
 ]
```
