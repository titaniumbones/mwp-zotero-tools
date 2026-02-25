;;; zotero-api.el --- Zotero Local API client for Emacs -*- lexical-binding: t; -*-

;; Copyright (C) 2025

;; Author: Matt Price
;; Keywords: zotero, research, bibliography
;; Version: 0.5.0
;; Package-Requires: ((emacs "25.1") (request "0.3.2") (json "1.4"))

;;; Commentary:

;; This package provides functions to interact with Zotero's local API
;; for retrieving items, collections, and annotations from your Zotero library.
;;
;; Key features:
;; - Retrieve items and collections from personal and group libraries
;; - Extract annotations from PDF attachments
;; - Format annotations as org-mode text
;; - Generate Zotero links with page numbers
;;
;; Usage:
;; (require 'zotero-api)
;; (zotero-get-items)
;; (zotero-get-annotations-for-item "ITEM_ID")

;;; Code:

(require 'request)
(require 'json)
(require 'url-util)

;;; Custom variables

(defgroup zotero nil
  "Zotero API integration for Emacs."
  :group 'external
  :prefix "zotero-")

(defcustom zotero-base-url "http://localhost:23119"
  "Base URL for Zotero local API."
  :type 'string
  :group 'zotero)

(defcustom zotero-default-user-id "0"
  "Default user ID for Zotero API calls (0 = current logged-in user)."
  :type 'string
  :group 'zotero)

(defcustom zotero-cli-directory nil
  "Path to the zotero-cli package directory.
When set, enables chapter grouping of annotations via the Python
`zotero-chapter-map' command.  When nil, chapter grouping is
disabled but everything else works."
  :type '(choice (const :tag "Disabled" nil)
                 (directory :tag "Directory"))
  :group 'zotero)

;;; Core API functions

(defun zotero--json-parse ()
  "Parse JSON at point using the native parser for correct UTF-8 handling.
Falls back to `json-read' when `json-parse-buffer' is unavailable."
  (if (fboundp 'json-parse-buffer)
      (json-parse-buffer :object-type 'alist :array-type 'array
                         :null-object nil :false-object nil)
    (json-read)))

(defun zotero--make-request (endpoint &optional callback)
  "Make a GET request to Zotero API ENDPOINT.
If CALLBACK is provided, make asynchronous request, otherwise synchronous.
Returns parsed JSON response or nil on error."
  (let ((url (concat zotero-base-url "/api" endpoint)))
    (if callback
        ;; Asynchronous request
        (request url
                 :type "GET"
                 :parser #'zotero--json-parse
                 :success (cl-function
                           (lambda (&key data &allow-other-keys)
                             (funcall callback data)))
                 :error (cl-function
                         (lambda (&key error-thrown &allow-other-keys)
                           (message "Zotero API error: %s" error-thrown)
                           (funcall callback nil))))
      ;; Synchronous request
      (condition-case err
          (with-current-buffer
              (url-retrieve-synchronously url t nil 10)
            (goto-char (point-min))
            (when (re-search-forward "^HTTP/[0-9\\.]+ 200" nil t)
              (re-search-forward "^$" nil t)
              (forward-char 1)
              (zotero--json-parse)))
        (error
         (message "Zotero API request failed: %s" (error-message-string err))
         nil)))))

(defun zotero-get-item (item-id &optional library-id)
  "Get a single item by ITEM-ID.
If LIBRARY-ID is provided, get from group library, otherwise from personal library."
  (let ((endpoint (if library-id
                      (format "/groups/%s/items/%s" library-id item-id)
                    (format "/users/%s/items/%s" zotero-default-user-id item-id))))
    (zotero--make-request endpoint)))

(defun zotero-get-item-children (item-id &optional library-id)
  "Get all children of an item (attachments, notes, etc.) by ITEM-ID.
If LIBRARY-ID is provided, get from group library, otherwise from personal library."
  (let ((endpoint (if library-id
                      (format "/groups/%s/items/%s/children" library-id item-id)
                    (format "/users/%s/items/%s/children" zotero-default-user-id item-id))))
    (let ((response (zotero--make-request endpoint)))
      (if (vectorp response) (append response nil) response))))

(defun zotero-get-items (&optional library-id limit item-type)
  "Get items from a library.
LIBRARY-ID: Library/group ID (nil for personal library)
LIMIT: Maximum number of items to return (default 25)
ITEM-TYPE: Filter by item type (e.g., 'book', 'journalArticle')"
  (let* ((limit (or limit 25))
         (params (format "?limit=%d" limit))
         (params (if item-type
                     (concat params "&itemType=" item-type)
                   params))
         (endpoint (if library-id
                       (format "/groups/%s/items%s" library-id params)
                     (format "/users/%s/items%s" zotero-default-user-id params))))
    (let ((response (zotero--make-request endpoint)))
      (if (vectorp response) (append response nil) response))))

(defun zotero-get-top-level-items (&optional library-id limit)
  "Get top-level items (excluding child items like attachments).
LIBRARY-ID: Library/group ID (nil for personal library)
LIMIT: Maximum number of items to return (default 25)"
  (let* ((limit (or limit 25))
         (params (format "?limit=%d&top=1" limit))
         (endpoint (if library-id
                       (format "/groups/%s/items%s" library-id params)
                     (format "/users/%s/items%s" zotero-default-user-id params))))
    (let ((response (zotero--make-request endpoint)))
      (if (vectorp response) (append response nil) response))))

(defun zotero-get-collections (&optional library-id)
  "Get all collections from a library.
LIBRARY-ID: Library/group ID (nil for personal library)"
  (let ((endpoint (if library-id
                      (format "/groups/%s/collections" library-id)
                    (format "/users/%s/collections" zotero-default-user-id))))
    (let ((response (zotero--make-request endpoint)))
      (if (vectorp response) (append response nil) response))))

(defun zotero-get-libraries ()
  "Get all libraries (groups) available in Zotero."
  (let ((endpoint (format "/users/%s/groups" zotero-default-user-id)))
    (let ((response (zotero--make-request endpoint)))
      (if (vectorp response) (append response nil) response))))

(defun zotero-get-library-info (library-id)
  "Get detailed information about a specific library/group by LIBRARY-ID."
  (let ((endpoint (format "/groups/%s" library-id)))
    (zotero--make-request endpoint)))

(defun zotero-get-item-types ()
  "Get all available item types."
  (let ((response (zotero--make-request "/itemTypes")))
    (if (vectorp response) (append response nil) response)))

;;; PDF and annotation functions

(defun zotero-get-file-attachments (item-id &optional library-id content-types)
  "Get file attachments of specified types for ITEM-ID.
LIBRARY-ID: Library/group ID (nil for personal library).
CONTENT-TYPES: List of MIME types to include.
Defaults to PDF and EPUB."
  (let* ((children (zotero-get-item-children item-id library-id))
         (allowed (or content-types '("application/pdf" "application/epub+zip")))
         (attachments '()))
    (dolist (child children)
      (let* ((data (cdr (assq 'data child)))
             (item-type (cdr (assq 'itemType data)))
             (content-type (cdr (assq 'contentType data))))
        (when (and (string= item-type "attachment")
                   (member content-type allowed))
          (push child attachments))))
    (nreverse attachments)))

(defun zotero-get-pdf-attachments (item-id &optional library-id)
  "Get all PDF attachments for a given item by ITEM-ID.
LIBRARY-ID: Library/group ID (nil for personal library)."
  (zotero-get-file-attachments item-id library-id '("application/pdf")))

(defun zotero-get-attachment-annotations (attachment-id &optional library-id)
  "Get all annotations for a PDF attachment by ATTACHMENT-ID.
LIBRARY-ID: Library/group ID (nil for personal library)"
  (let ((annotations '()))
    ;; First try the standard approach - get children of the attachment
    (let* ((endpoint (if library-id
                         (format "/groups/%s/items/%s/children" library-id attachment-id)
                       (format "/users/%s/items/%s/children" zotero-default-user-id attachment-id)))
           (response (zotero--make-request endpoint)))
      (when (vectorp response)
        (dolist (item (append response nil))
          (let* ((data (cdr (assq 'data item)))
                 (item-type (cdr (assq 'itemType data))))
            (when (string= item-type "annotation")
              (push item annotations))))))

    ;; If no annotations found as children, try alternative approach:
    ;; Look for annotation items where parentItem matches our attachment-id
    (when (null annotations)
      (let ((annotation-items (zotero-get-items library-id 1000 "annotation")))
        (dolist (item annotation-items)
          (let* ((data (cdr (assq 'data item)))
                 (parent-item (cdr (assq 'parentItem data))))
            (when (string= parent-item attachment-id)
              (push item annotations))))))

    (nreverse annotations)))

(defun zotero-get-all-annotations-for-item (item-id &optional library-id)
  "Get all annotations from all PDF attachments for a given item by ITEM-ID.
LIBRARY-ID: Library/group ID (nil for personal library)
Returns an alist with item info and all annotations organized by attachment."
  (let* ((item (zotero-get-item item-id library-id))
         (result '()))

    (if (not item)
        (list (cons 'error (format "Item %s not found" item-id)))

      (let* ((item-data (cdr (assq 'data item)))
             (item-title (or (cdr (assq 'title item-data)) "Unknown"))
             (item-type (or (cdr (assq 'itemType item-data)) "Unknown"))
             (file-attachments (zotero-get-file-attachments item-id library-id))
             (attachments '()))

        (dolist (attachment file-attachments)
          (let* ((attachment-id (cdr (assq 'key attachment)))
                 (attachment-data (cdr (assq 'data attachment)))
                 (attachment-title (or (cdr (assq 'title attachment-data)) "Unknown"))
                 (filename (or (cdr (assq 'filename attachment-data)) "Unknown"))
                 (annotations (zotero-get-attachment-annotations attachment-id library-id)))

            (push (list (cons 'attachment-id attachment-id)
                        (cons 'attachment-title attachment-title)
                        (cons 'filename filename)
                        (cons 'annotations-count (length annotations))
                        (cons 'annotations annotations))
                  attachments)))

        (list (cons 'item-id item-id)
              (cons 'item-title item-title)
              (cons 'item-type item-type)
              (cons 'attachments (nreverse attachments)))))))

;;; Annotation sorting and helpers

(defun zotero-sort-annotations (annotations)
  "Sort ANNOTATIONS by `annotationSortIndex' in reading order.
Falls back to zero-padded `annotationPageLabel'."
  (sort (copy-sequence annotations)
        (lambda (a b)
          (let ((idx-a (zotero--annotation-sort-key a))
                (idx-b (zotero--annotation-sort-key b)))
            (string< idx-a idx-b)))))

(defun zotero--annotation-sort-key (annotation)
  "Return sort key string for ANNOTATION."
  (let* ((data (cdr (assq 'data annotation)))
         (idx (or (cdr (assq 'annotationSortIndex data)) "")))
    (if (and idx (not (string-empty-p idx)))
        idx
      (let ((page (or (cdr (assq 'annotationPageLabel data)) "0")))
        (condition-case nil
            (format "%05d" (string-to-number page))
          (error "99999"))))))

(defun zotero--is-spine-index (label)
  "Check if LABEL looks like an EPUB spine index (zero-padded digits, 5+ chars)."
  (and label
       (not (string-empty-p label))
       (string-match-p "\\`[0-9]+\\'" label)
       (>= (length label) 5)))

(defun zotero--build-open-pdf-link (attachment-id page-label annotation-key)
  "Build a zotero://open-pdf link for ATTACHMENT-ID.
PAGE-LABEL and ANNOTATION-KEY are optional URL params."
  (let ((link (concat "zotero://open-pdf/library/items/" attachment-id))
        (params '()))
    (when (and page-label (not (string-empty-p page-label)))
      (push (concat "page=" page-label) params))
    (when (and annotation-key (not (string-empty-p annotation-key)))
      (push (concat "annotation=" annotation-key) params))
    (when params
      (setq link (concat link "?" (mapconcat #'identity (nreverse params) "&"))))
    link))

(defun zotero--page-display (page-label sort-index)
  "Compute page display text from PAGE-LABEL and SORT-INDEX."
  (cond
   ((and page-label (not (string-empty-p page-label))
         (not (zotero--is-spine-index page-label)))
    (format "p. %s" page-label))
   ((and (or (not page-label) (string-empty-p page-label))
         sort-index (string-match-p "|" sort-index))
    "annotation")
   ((or (not page-label) (string-empty-p page-label))
    "p. ?")
   (t "annotation")))

;;; Chapter map integration (via Python CLI)

(defun zotero--resolve-attachment-path (attachment-id filename)
  "Construct the Zotero storage path for ATTACHMENT-ID and FILENAME."
  (let ((storage-dir (expand-file-name "~/Zotero/storage")))
    (expand-file-name filename (expand-file-name attachment-id storage-dir))))

(defun zotero--get-chapter-map (file-path)
  "Get chapter map for FILE-PATH by calling the Python CLI.
Returns a list of (title page-label level) lists, or nil on failure.
Requires `zotero-cli-directory' to be set."
  (when (and zotero-cli-directory
             (file-exists-p file-path))
    (condition-case nil
        (let* ((cmd (format "uv run --directory %s zotero-chapter-map %s"
                            (shell-quote-argument
                             (expand-file-name zotero-cli-directory))
                            (shell-quote-argument
                             (expand-file-name file-path))))
               (output (string-trim (shell-command-to-string cmd))))
          (when (and output (not (string-empty-p output)))
            (let ((parsed (json-parse-string output :array-type 'list)))
              ;; Convert inner arrays to lists
              (mapcar (lambda (entry)
                        (if (vectorp entry) (append entry nil) entry))
                      parsed))))
      (error nil))))

(defun zotero--get-chapter-map-for-attachment (attachment-id filename)
  "Get chapter map for an attachment given ATTACHMENT-ID and FILENAME.
Returns chapter map list or nil."
  (let ((path (zotero--resolve-attachment-path attachment-id filename)))
    (when (file-exists-p path)
      (zotero--get-chapter-map path))))

(defun zotero--get-chapters-for-page (chapter-map page-label)
  "Find ancestor chapter headings for PAGE-LABEL in CHAPTER-MAP.
CHAPTER-MAP is a list of (title page-label level) entries.
Returns list of (title level) sorted by level, or nil."
  (when (and chapter-map page-label (not (string-empty-p page-label)))
    (let ((target (condition-case nil (string-to-number page-label) (error nil))))
      (if (and target (/= target 0))
          ;; Numeric comparison
          (let ((nearest-by-level (make-hash-table :test 'eql)))
            (dolist (entry chapter-map)
              (let* ((title (nth 0 entry))
                     (lbl (nth 1 entry))
                     (level (nth 2 entry))
                     (page-num (condition-case nil
                                   (string-to-number
                                    (if (stringp lbl) lbl (number-to-string lbl)))
                                 (error nil))))
                (when (and page-num (<= page-num target))
                  (puthash level title nearest-by-level)
                  ;; Clear deeper levels
                  (maphash (lambda (k _v)
                             (when (> k level)
                               (remhash k nearest-by-level)))
                           nearest-by-level))))
            (let ((result '()))
              (maphash (lambda (level title)
                         (push (list title level) result))
                       nearest-by-level)
              (sort result (lambda (a b) (< (nth 1 a) (nth 1 b))))))
        ;; Non-numeric: exact match
        (let ((found nil))
          (dolist (entry chapter-map)
            (let ((title (nth 0 entry))
                  (lbl (nth 1 entry))
                  (level (nth 2 entry)))
              (when (equal (if (stringp lbl) lbl "") page-label)
                (setq found (list (list title level))))))
          found)))))

;;; Org-mode formatting

(defun zotero-normalize-text-encoding (text)
  "Fix common UTF-8/Latin-1 encoding issues in annotation text.
TEXT is the raw text that may have encoding issues.
Returns text with corrected character encoding."
  (if (not text)
      text
    (let ((replacements
           '(;; Smart quotes and dashes
             ("â" . "\"")    ; Left double quotation mark
             ("â" . "\"")    ; Right double quotation mark
             ("â" . "'")     ; Left single quotation mark
             ("â" . "'")     ; Right single quotation mark
             ("â" . "—")     ; Em dash
             ("â" . "–")     ; En dash

             ;; Accented characters
             ("Ã¡" . "á")    ; a with acute
             ("Ã©" . "é")    ; e with acute
             ("Ã­" . "í")    ; i with acute
             ("Ã³" . "ó")    ; o with acute
             ("Ãº" . "ú")    ; u with acute
             ("Ã±" . "ñ")    ; n with tilde
             ("Ã" . "À")     ; A with grave
             ("Ã¨" . "è")    ; e with grave
             ("Ã¬" . "ì")    ; i with grave
             ("Ã²" . "ò")    ; o with grave
             ("Ã¹" . "ù")    ; u with grave
             ("Ã¤" . "ä")    ; a with diaeresis
             ("Ã«" . "ë")    ; e with diaeresis
             ("Ã¯" . "ï")    ; i with diaeresis
             ("Ã¶" . "ö")    ; o with diaeresis
             ("Ã¼" . "ü")    ; u with diaeresis
             ("Ã§" . "ç")    ; c with cedilla

             ;; Other common issues
             ("â¢" . "•")    ; Bullet point
             ("â¦" . "…")    ; Horizontal ellipsis
             ("Â°" . "°")    ; Degree symbol
             ("Â±" . "±")    ; Plus-minus sign
             ("Â²" . "²")    ; Superscript 2
             ("Â³" . "³")    ; Superscript 3
             ("Â½" . "½")    ; Fraction 1/2
             ("Â¼" . "¼")    ; Fraction 1/4
             ("Â¾" . "¾")    ; Fraction 3/4
             ("Â©" . "©")    ; Copyright symbol
             ("Â®" . "®")    ; Registered trademark
             ("â¹" . "‹")    ; Single left-pointing angle quotation mark
             ("âº" . "›")    ; Single right-pointing angle quotation mark
             ("Â«" . "«")    ; Left-pointing double angle quotation mark
             ("Â»" . "»")    ; Right-pointing double angle quotation mark

             ;; Additional problematic sequences seen in the data
             ("peÂºple" . "people")
             ("pe\"ºple" . "people")     ; Alternative corruption pattern
             ("Ã©lite" . "élite")
             ("Ã±res" . "fires")
             ("dÃ©cor" . "décor")
             ("signiÃ±cant" . "significant")
             ("deÃ±ciencies" . "deficiencies")
             ("proÃ±tability" . "profitability")
             ("contempoâraries" . "contemporaries")
             ("contempo\"raries" . "contemporaries")  ; Alternative corruption pattern
             ("houseâhold" . "household")
             ("âassociationistsâ" . "\"associationists\"")
             ("âplace\"" . "\"place\"")
             ("âpurchasing\"" . "\"purchasing\"")
             ("âmaintain-ing" . "\"maintain-ing")
             ("âdecentlyâ" . "\"decently\"")
             ("âseparate spheres.'â" . "\"separate spheres.'\"")
             ("heartâ is" . "heart\" is")  ; Specific corrupted quote pattern
             ("âdogs" . "\"dogs")  ; Specific corrupted quote pattern

             ;; Additional corruption patterns found in the data
             ("as;9" . "as-")           ; Common corruption pattern
             ("as;9 " . "as- ")         ; Common corruption pattern with space
             ("pa5-checks" . "paychecks")  ; Specific corruption
             ("th%\\." . "they.")       ; Corruption with punctuation
             ("th% " . "they ")         ; Corruption with space
             ("th%" . "they")           ; Corruption without space
             ("undenl" . "under")       ; Truncated/corrupted word
             ("peºple" . "people")      ; Specific corruption with ordinal symbol
             ("contempo—raries" . "contemporaries")  ; Specific corruption
             ("contempo\"raries" . "contemporaries")  ; Alternative corruption pattern

             ;; Smart quote corruption patterns (where " appears inappropriately)
             ("ex\"pected" . "expected")    ; Specific corruption in text
             ("house\"hold" . "household")  ; Specific corruption
             ("house\"wives" . "housewives") ; Specific corruption
             ("single\"family" . "single-family")  ; Specific corruption
             ("well\"publicized" . "well-publicized")  ; Specific corruption
             ("ration-ali'ze" . "rationalize")  ; Specific corruption with apostrophe
             ("car\"ried" . "carried")     ; Specific corruption
             ("in\"dustrialization" . "industrialization")  ; Specific corruption
             ("self\"sufficient" . "self-sufficient")  ; Specific corruption
             ("water\"cooled" . "water-cooled")  ; Specific corruption
             ("home\"places" . "home places")  ; Specific corruption - add space
             ("work\"places" . "work places")  ; Specific corruption - add space
             ("rules\"to" . "rules—to")    ; Em-dash corruption (rules" should be rules—)
             ("ourselves\"generate" . "ourselves—generate")  ; Em-dash corruption
             ("home\"namely" . "home—namely")  ; Em-dash corruption

             ;; UTF-8 corruption patterns with specific byte sequences
             ("rules\"\x80\x94to" . "rules—to")    ; Specific UTF-8 corrupted em-dash
             ("ourselves\"\x80\x94generate" . "ourselves—generate")  ; UTF-8 corrupted em-dash
             ("home\"\x80\x94namely" . "home—namely")  ; UTF-8 corrupted em-dash
             )))
      ;; First apply exact string replacements
      (dolist (replacement replacements)
        (setq text (replace-regexp-in-string
                    (regexp-quote (car replacement))
                    (cdr replacement)
                    text t t)))

      ;; Then apply regex patterns for more complex corruptions
      (setq text (replace-regexp-in-string
                  "rules\"[^a-zA-Z]*to" "rules—to" text t t))
      (setq text (replace-regexp-in-string
                  "ourselves\"[^a-zA-Z]*generate" "ourselves—generate" text t t))
      (setq text (replace-regexp-in-string
                  "home\"[^a-zA-Z]*namely" "home—namely" text t t))
      text)))

(defun zotero--format-single-annotation-org (annotation attachment-id &optional citation-key)
  "Format a single ANNOTATION as org-mode lines.
ATTACHMENT-ID is the parent attachment key.
CITATION-KEY is optional BibTeX key for citations.
Returns a list of strings."
  (let* ((ann-data (cdr (assq 'data annotation)))
         (ann-type (or (cdr (assq 'annotationType ann-data)) "unknown"))
         (ann-key (or (cdr (assq 'key ann-data)) ""))
         (text (zotero-normalize-text-encoding (cdr (assq 'annotationText ann-data))))
         (comment (zotero-normalize-text-encoding (cdr (assq 'annotationComment ann-data))))
         (page-label (or (cdr (assq 'annotationPageLabel ann-data)) ""))
         (sort-index (or (cdr (assq 'annotationSortIndex ann-data)) ""))
         (tags (cdr (assq 'tags ann-data)))
         (page-display (zotero--page-display page-label sort-index))
         (zotero-link (zotero--build-open-pdf-link attachment-id page-label ann-key))
         (lines '()))
    (cond
     ;; highlight/underline
     ((member ann-type '("highlight" "underline"))
      (when (and text (not (string-empty-p text)))
        (push (format "[[%s][%s]]:" zotero-link page-display) lines)
        (push "#+begin_quote" lines)
        (push text lines)
        (push "#+end_quote" lines)
        (when (and comment (not (string-empty-p comment)))
          (push "" lines)
          (push comment lines))
        (when citation-key
          (let ((page-info (if (and page-label (not (string-empty-p page-label)))
                               page-label "?")))
            (push "" lines)
            (push (format "[cite:@%s, p.%s]" citation-key page-info) lines)))))
     ;; note
     ((string= ann-type "note")
      (push (format "[[%s][%s]]:" zotero-link page-display) lines)
      (when (and comment (not (string-empty-p comment)))
        (push "#+begin_comment" lines)
        (push comment lines)
        (push "#+end_comment" lines)))
     ;; image
     ((string= ann-type "image")
      (push (format "[[%s][%s]]:" zotero-link page-display) lines)
      (push "#+begin_example" lines)
      (push "[Image annotation]" lines)
      (push "#+end_example" lines)
      (when (and comment (not (string-empty-p comment)))
        (push "" lines)
        (push comment lines))))
    ;; Tags
    (when (and tags (listp tags))
      (let ((tag-names (delq nil (mapcar (lambda (t) (cdr (assq 'tag t))) tags))))
        (when tag-names
          (push (concat ":" (mapconcat #'identity tag-names ":") ":") lines))))
    (nreverse lines)))

(defun zotero-format-as-org-mode (annotations-data &optional citation-key)
  "Format ANNOTATIONS-DATA as org-mode text with per-annotation structure.
ANNOTATIONS-DATA should be the result from `zotero-get-all-annotations-for-item'.
CITATION-KEY is optional BibTeX citation key for org-cite format.
Each annotation gets its own block with a zotero://open-pdf link."
  (let ((error-msg (cdr (assq 'error annotations-data))))
    (if error-msg
        (format "# Error: %s\n" error-msg)

      (let* ((item-title (zotero-normalize-text-encoding (cdr (assq 'item-title annotations-data))))
             (item-type (cdr (assq 'item-type annotations-data)))
             (item-id (cdr (assq 'item-id annotations-data)))
             (attachments (cdr (assq 'attachments annotations-data)))
             (multi-attachment (> (length attachments) 1))
             (org-content '()))

        ;; Main header with item info
        (push (format "* %s" item-title) org-content)
        (push "  :PROPERTIES:" org-content)
        (push (format "  :ITEM_TYPE: %s" item-type) org-content)
        (push (format "  :ZOTERO_KEY: %s" item-id) org-content)
        (when citation-key
          (push (format "  :CUSTOM_ID: %s" citation-key) org-content))
        (push "  :END:" org-content)
        (push "" org-content)

        ;; Process each attachment
        (dolist (attachment attachments)
          (let* ((attachment-title (zotero-normalize-text-encoding (cdr (assq 'attachment-title attachment))))
                 (attachment-id (cdr (assq 'attachment-id attachment)))
                 (filename (or (cdr (assq 'filename attachment)) ""))
                 (annotations (cdr (assq 'annotations attachment))))

            ;; Attachment header only for multi-attachment
            (when multi-attachment
              (push (format "** %s" attachment-title) org-content)
              (push "" org-content))

            (if (null annotations)
                (progn
                  (push (if multi-attachment "   No annotations found." "No annotations found.") org-content)
                  (push "" org-content))

              ;; Sort annotations
              (let* ((sorted-anns (zotero-sort-annotations annotations))
                     (chapter-map (zotero--get-chapter-map-for-attachment
                                   attachment-id filename))
                     (current-chapters (make-hash-table :test 'eql))
                     (chapter-heading-base (if multi-attachment "**" "*")))
                (dolist (annotation sorted-anns)
                  ;; Chapter grouping
                  (when chapter-map
                    (let* ((ann-data (cdr (assq 'data annotation)))
                           (page-label (or (cdr (assq 'annotationPageLabel ann-data)) ""))
                           (sort-index (or (cdr (assq 'annotationSortIndex ann-data)) ""))
                           ;; For EPUB, use first field of sortIndex as page label
                           (effective-label
                            (if (and (zotero--is-spine-index page-label)
                                     (string-match "\\`\\([0-9]+\\)" sort-index))
                                (match-string 1 sort-index)
                              page-label))
                           (chapters (zotero--get-chapters-for-page
                                      chapter-map effective-label)))
                      (dolist (ch chapters)
                        (let ((title (nth 0 ch))
                              (level (nth 1 ch)))
                          (unless (equal (gethash level current-chapters) title)
                            (puthash level title current-chapters)
                            ;; Clear deeper levels
                            (maphash (lambda (k _v)
                                       (when (> k level)
                                         (remhash k current-chapters)))
                                     current-chapters)
                            (push (format "%s%s %s"
                                          chapter-heading-base
                                          (make-string level ?*)
                                          title)
                                  org-content)
                            (push "" org-content))))))
                  (let ((ann-lines (zotero--format-single-annotation-org
                                    annotation attachment-id citation-key)))
                    (when ann-lines
                      (dolist (line ann-lines)
                        (push line org-content))
                      (push "" org-content))))))))

        (mapconcat #'identity (nreverse org-content) "\n")))))

(defun zotero--format-single-annotation-md (annotation attachment-id &optional citation-key)
  "Format a single ANNOTATION as markdown lines.
ATTACHMENT-ID is the parent attachment key.
CITATION-KEY is optional BibTeX key for citations.
Returns a list of strings."
  (let* ((ann-data (cdr (assq 'data annotation)))
         (ann-type (or (cdr (assq 'annotationType ann-data)) "unknown"))
         (ann-key (or (cdr (assq 'key ann-data)) ""))
         (text (zotero-normalize-text-encoding (cdr (assq 'annotationText ann-data))))
         (comment (zotero-normalize-text-encoding (cdr (assq 'annotationComment ann-data))))
         (page-label (or (cdr (assq 'annotationPageLabel ann-data)) ""))
         (sort-index (or (cdr (assq 'annotationSortIndex ann-data)) ""))
         (tags (cdr (assq 'tags ann-data)))
         (page-display (zotero--page-display page-label sort-index))
         (zotero-link (zotero--build-open-pdf-link attachment-id page-label ann-key))
         (lines '()))
    (cond
     ;; highlight/underline
     ((member ann-type '("highlight" "underline"))
      (when (and text (not (string-empty-p text)))
        (push (format "[%s](%s):" page-display zotero-link) lines)
        (push "" lines)
        (push (format "> %s" text) lines)
        (when (and comment (not (string-empty-p comment)))
          (push "" lines)
          (push comment lines))
        (when citation-key
          (let ((page-info (if (and page-label (not (string-empty-p page-label)))
                               page-label "?")))
            (push "" lines)
            (push (format "[cite:@%s, p.%s]" citation-key page-info) lines)))))
     ;; note
     ((string= ann-type "note")
      (push (format "[%s](%s):" page-display zotero-link) lines)
      (when (and comment (not (string-empty-p comment)))
        (push "" lines)
        (push (format "*%s*" comment) lines)))
     ;; image
     ((string= ann-type "image")
      (push (format "[%s](%s):" page-display zotero-link) lines)
      (push "" lines)
      (push "`[Image annotation]`" lines)
      (when (and comment (not (string-empty-p comment)))
        (push "" lines)
        (push comment lines))))
    ;; Tags
    (when (and tags (listp tags))
      (let ((tag-names (delq nil (mapcar (lambda (t) (cdr (assq 'tag t))) tags))))
        (when tag-names
          (push "" lines)
          (push (concat "Tags: " (mapconcat (lambda (t) (format "`%s`" t)) tag-names ", ")) lines))))
    (nreverse lines)))

(defun zotero-format-as-markdown (annotations-data &optional citation-key)
  "Format ANNOTATIONS-DATA as markdown with per-annotation structure.
ANNOTATIONS-DATA should be the result from `zotero-get-all-annotations-for-item'.
CITATION-KEY is optional BibTeX citation key for citations.
Each annotation gets its own blockquote with a zotero link."
  (let ((error-msg (cdr (assq 'error annotations-data))))
    (if error-msg
        (format "# Error: %s\n" error-msg)

      (let* ((item-title (zotero-normalize-text-encoding (cdr (assq 'item-title annotations-data))))
             (item-type (cdr (assq 'item-type annotations-data)))
             (item-id (cdr (assq 'item-id annotations-data)))
             (attachments (cdr (assq 'attachments annotations-data)))
             (multi-attachment (> (length attachments) 1))
             (md-content '()))

        ;; Main header with item info
        (push (format "# %s" item-title) md-content)
        (push "" md-content)
        (push (format "**Item Type:** %s" item-type) md-content)
        (push (format "**Zotero Key:** %s" item-id) md-content)
        (when citation-key
          (push (format "**Citation Key:** %s" citation-key) md-content))
        (push "" md-content)

        ;; Process each attachment
        (dolist (attachment attachments)
          (let* ((attachment-title (zotero-normalize-text-encoding (cdr (assq 'attachment-title attachment))))
                 (attachment-id (cdr (assq 'attachment-id attachment)))
                 (filename (or (cdr (assq 'filename attachment)) ""))
                 (annotations (cdr (assq 'annotations attachment))))

            ;; Attachment header only for multi-attachment
            (when multi-attachment
              (push (format "## %s" attachment-title) md-content)
              (push "" md-content))

            (if (null annotations)
                (progn
                  (push "No annotations found." md-content)
                  (push "" md-content))

              ;; Sort annotations
              (let* ((sorted-anns (zotero-sort-annotations annotations))
                     (chapter-map (zotero--get-chapter-map-for-attachment
                                   attachment-id filename))
                     (current-chapters (make-hash-table :test 'eql))
                     (chapter-heading-base (if multi-attachment "##" "#")))
                (dolist (annotation sorted-anns)
                  ;; Chapter grouping
                  (when chapter-map
                    (let* ((ann-data (cdr (assq 'data annotation)))
                           (page-label (or (cdr (assq 'annotationPageLabel ann-data)) ""))
                           (sort-index (or (cdr (assq 'annotationSortIndex ann-data)) ""))
                           (effective-label
                            (if (and (zotero--is-spine-index page-label)
                                     (string-match "\\`\\([0-9]+\\)" sort-index))
                                (match-string 1 sort-index)
                              page-label))
                           (chapters (zotero--get-chapters-for-page
                                      chapter-map effective-label)))
                      (dolist (ch chapters)
                        (let ((title (nth 0 ch))
                              (level (nth 1 ch)))
                          (unless (equal (gethash level current-chapters) title)
                            (puthash level title current-chapters)
                            (maphash (lambda (k _v)
                                       (when (> k level)
                                         (remhash k current-chapters)))
                                     current-chapters)
                            (push (format "%s%s %s"
                                          chapter-heading-base
                                          (make-string level ?#)
                                          title)
                                  md-content)
                            (push "" md-content))))))
                  (let ((ann-lines (zotero--format-single-annotation-md
                                    annotation attachment-id citation-key)))
                    (when ann-lines
                      (dolist (line ann-lines)
                        (push line md-content))
                      (push "" md-content))))))))

        (mapconcat #'identity (nreverse md-content) "\n")))))

;;; Interactive functions

;;;###autoload
(defun zotero-insert-item-annotations (item-id)
  "Insert annotations for ITEM-ID at point in org-mode format."
  (interactive "sZotero Item ID: ")
  (let* ((annotations-data (zotero-get-all-annotations-for-item item-id))
         (citation-key (zotero-get-citation-key-for-item item-id))
         (org-content (zotero-format-as-org-mode annotations-data citation-key)))
    (insert org-content)))

;;;###autoload
(defun zotero-save-item-annotations-to-file (item-id filename)
  "Save annotations for ITEM-ID to FILENAME in org-mode format."
  (interactive "sZotero Item ID: \nFSave to file: ")
  (let* ((annotations-data (zotero-get-all-annotations-for-item item-id))
         (citation-key (zotero-get-citation-key-for-item item-id))
         (org-content (zotero-format-as-org-mode annotations-data citation-key)))
    (with-temp-file filename
      (insert org-content))
    (message "Annotations saved to %s" filename)))

;;;###autoload
(defun zotero-insert-item-annotations-markdown (item-id)
  "Insert annotations for ITEM-ID at point in markdown format."
  (interactive "sZotero Item ID: ")
  (let* ((annotations-data (zotero-get-all-annotations-for-item item-id))
         (citation-key (zotero-get-citation-key-for-item item-id))
         (md-content (zotero-format-as-markdown annotations-data citation-key)))
    (insert md-content)))

;;;###autoload
(defun zotero-save-item-annotations-to-markdown-file (item-id filename)
  "Save annotations for ITEM-ID to FILENAME in markdown format."
  (interactive "sZotero Item ID: \nFSave to file: ")
  (let* ((annotations-data (zotero-get-all-annotations-for-item item-id))
         (citation-key (zotero-get-citation-key-for-item item-id))
         (md-content (zotero-format-as-markdown annotations-data citation-key)))
    (with-temp-file filename
      (insert md-content))
    (message "Annotations saved to %s" filename)))

;;;###autoload
(defun zotero-browse-libraries ()
  "Browse Zotero libraries and display basic information."
  (interactive)
  (let ((libraries (zotero-get-libraries)))
    (with-output-to-temp-buffer "*Zotero Libraries*"
      (princ (format "Found %d libraries:\n\n" (length libraries)))
      (dolist (library libraries)
        (let* ((id (cdr (assq 'id library)))
               (name (cdr (assq 'name library)))
               (type (cdr (assq 'type library))))
          (princ (format "ID: %s\nName: %s\nType: %s\n\n" id name type)))))))

;;;###autoload
(defun zotero-browse-items (&optional library-id limit)
  "Browse Zotero items and display basic information.
LIBRARY-ID: Library/group ID (nil for personal library)
LIMIT: Maximum number of items to show (default 25)"
  (interactive)
  (let* ((limit (or limit 25))
         (items (zotero-get-top-level-items library-id limit)))
    (with-output-to-temp-buffer "*Zotero Items*"
      (princ (format "Found %d items:\n\n" (length items)))
      (dolist (item items)
        (let* ((key (cdr (assq 'key item)))
               (data (cdr (assq 'data item)))
               (title (or (cdr (assq 'title data)) "Unknown"))
               (item-type (or (cdr (assq 'itemType data)) "Unknown")))
          (princ (format "Key: %s\nTitle: %s\nType: %s\n\n" key title item-type)))))))

;;; Better BibTeX integration

(defvar zotero--bbt-available nil
  "Cached BBT availability status.  nil = unchecked, t or `unavailable'.")

(defun zotero--bbt-available-p ()
  "Check if Better BibTeX is running.
Caches the result so subsequent calls are instant."
  (if (eq zotero--bbt-available 'unavailable)
      nil
    (or zotero--bbt-available
        (condition-case nil
            (let ((url (concat "http://127.0.0.1:"
                               (car (split-string
                                     (replace-regexp-in-string
                                      "https?://[^:]+:" ""
                                      zotero-base-url)
                                     "/"))
                               "/better-bibtex/cayw?probe=true")))
              (with-current-buffer (url-retrieve-synchronously url t nil 5)
                (goto-char (point-min))
                (if (and (re-search-forward "^HTTP/[0-9\\.]+ 200" nil t)
                         (re-search-forward "\n\n" nil t)
                         (looking-at "ready"))
                    (setq zotero--bbt-available t)
                  (setq zotero--bbt-available 'unavailable)
                  nil)))
          (error
           (setq zotero--bbt-available 'unavailable)
           nil)))))

(defun zotero--bbt-json-rpc (method params)
  "Call BBT JSON-RPC METHOD with PARAMS.
Returns the `result' field from the response or nil on error."
  (let* ((port (car (split-string
                     (replace-regexp-in-string
                      "https?://[^:]+:" "" zotero-base-url)
                     "/")))
         (url (format "http://127.0.0.1:%s/better-bibtex/json-rpc" port))
         (payload (json-encode `((jsonrpc . "2.0")
                                 (method . ,method)
                                 (params . ,params)
                                 (id . 1))))
         (url-request-method "POST")
         (url-request-extra-headers '(("Content-Type" . "application/json")
                                      ("Accept" . "application/json")))
         (url-request-data (encode-coding-string payload 'utf-8)))
    (condition-case nil
        (with-current-buffer (url-retrieve-synchronously url t nil 10)
          (goto-char (point-min))
          (when (re-search-forward "^HTTP/[0-9\\.]+ 200" nil t)
            (re-search-forward "\n\n" nil t)
            (let ((response (zotero--json-parse)))
              (cdr (assq 'result response)))))
      (error nil))))

(defun zotero--bbt-get-citation-key (item-id &optional library-id)
  "Get citation key for ITEM-ID via BBT JSON-RPC.
LIBRARY-ID defaults to 1 (personal library).  BBT uses 1-based
library IDs, not the Zotero API's 0."
  (let* ((lib-id (or library-id "1"))
         (full-key (format "%s:%s" lib-id item-id))
         (result (zotero--bbt-json-rpc "item.citationkey"
                                       (vector (vector full-key)))))
    (when result
      (cdr (assoc full-key result)))))

(defun zotero-export-item-bibtex (item-id &optional library-id)
  "Export a single item as BibTeX.
ITEM-ID is the Zotero item ID.
LIBRARY-ID is optional library ID for group libraries.
Returns BibTeX string or nil if export failed."
  (let* ((endpoint (if library-id
                       (format "/groups/%s/items/%s" library-id item-id)
                     (format "/users/%s/items/%s" zotero-default-user-id item-id)))
         (url (format "%s/api%s?format=bibtex" zotero-base-url endpoint)))
    (condition-case err
        (let ((response (request url
                                 :type "GET"
                                 :sync t
                                 :timeout 10)))
          (when (eq (request-response-status-code response) 200)
            (string-trim (request-response-data response))))
      (error nil))))

(defun zotero-get-citation-key-for-item (item-id &optional library-id)
  "Get the BibTeX citation key for ITEM-ID.
Tries Better BibTeX JSON-RPC first (fast, direct), then falls back
to exporting BibTeX via native API and parsing with regex.
LIBRARY-ID is optional library ID for group libraries."
  ;; Try BBT first
  (or (and (zotero--bbt-available-p)
           (zotero--bbt-get-citation-key item-id library-id))
      ;; Fall back to BibTeX export
      (condition-case err
          (let ((bibtex-data (zotero-export-item-bibtex item-id library-id)))
            (when bibtex-data
              (when (string-match "@\\w+\\s-*{\\s-*\\([^,\\s-]+\\)\\s-*," bibtex-data)
                (match-string 1 bibtex-data))))
        (error
         (message "Error getting citation key for item %s: %s"
                  item-id (error-message-string err))
         nil))))

;;; Collection annotation functions

(defun zotero-get-collection-items (collection-id &optional library-id limit)
  "Get all items from a specific collection.
COLLECTION-ID is the Zotero collection ID.
LIBRARY-ID is the library/group ID (nil for personal library).
LIMIT is the maximum number of items to return (default 100)."
  (let* ((limit (or limit 100))
         (params (format "?limit=%d" limit))
         (endpoint (if library-id
                       (format "/groups/%s/collections/%s/items%s" library-id collection-id params)
                     (format "/users/%s/collections/%s/items%s" zotero-default-user-id collection-id params))))
    (let ((response (zotero--make-request endpoint)))
      (if (vectorp response) (append response nil) response))))

(defun zotero-get-collection-info (collection-id &optional library-id)
  "Get information about a specific collection.
COLLECTION-ID is the Zotero collection ID.
LIBRARY-ID is the library/group ID (nil for personal library).
Returns collection information alist or nil if not found."
  (let ((endpoint (if library-id
                      (format "/groups/%s/collections/%s" library-id collection-id)
                    (format "/users/%s/collections/%s" zotero-default-user-id collection-id))))
    (zotero--make-request endpoint)))

(defun zotero-get-all-collection-annotations (collection-id &optional library-id)
  "Get all annotations from all items in a collection.
COLLECTION-ID is the Zotero collection ID.
LIBRARY-ID is the library/group ID (nil for personal library).
Returns an alist containing collection info and all annotations organized by item."
  (let* ((collection-info (zotero-get-collection-info collection-id library-id)))
    (if (not collection-info)
        (list (cons 'error (format "Collection %s not found" collection-id)))

      (let* ((collection-items (zotero-get-collection-items collection-id library-id 1000))
             (collection-data (cdr (assq 'data collection-info)))
             (collection-name (or (cdr (assq 'name collection-data)) "Unknown"))
             (collection-parent (cdr (assq 'parentCollection collection-data)))
             (items-with-annotations '()))

        ;; Process each item in the collection
        (dolist (item collection-items)
          (let* ((item-id (cdr (assq 'key item)))
                 (item-data (cdr (assq 'data item)))
                 (item-type (cdr (assq 'itemType item-data))))

            ;; Skip attachments and annotations - we only want top-level items
            (unless (member item-type '("attachment" "note" "annotation"))
              ;; Get annotations for this item
              (let ((item-annotations (zotero-get-all-annotations-for-item item-id library-id)))
                ;; Only include items that have annotations
                (when (and (not (assq 'error item-annotations))
                           (cdr (assq 'attachments item-annotations)))
                  (let ((total-annotations 0))
                    (dolist (attachment (cdr (assq 'attachments item-annotations)))
                      (setq total-annotations (+ total-annotations (cdr (assq 'annotations-count attachment)))))
                    (when (> total-annotations 0)
                      (push item-annotations items-with-annotations))))))))

        (list (cons 'collection-id collection-id)
              (cons 'collection-name collection-name)
              (cons 'collection-parent collection-parent)
              (cons 'library-id library-id)
              (cons 'items-count (length collection-items))
              (cons 'items (nreverse items-with-annotations)))))))

(defun zotero-format-collection-annotations-as-org (collection-data)
  "Format collection annotation data as org-mode text.
COLLECTION-DATA should be the result from `zotero-get-all-collection-annotations'.
Returns formatted org-mode string."
  (let ((error-msg (cdr (assq 'error collection-data))))
    (if error-msg
        (format "# Error: %s\n" error-msg)

      (let* ((collection-name (zotero-normalize-text-encoding (cdr (assq 'collection-name collection-data))))
             (collection-id (cdr (assq 'collection-id collection-data)))
             (library-id (cdr (assq 'library-id collection-data)))
             (items-count (cdr (assq 'items-count collection-data)))
             (items (cdr (assq 'items collection-data)))
             (items-with-annotations (length items))
             (org-content '()))

        ;; Main collection header
        (push (format "* Collection: %s" collection-name) org-content)
        (push "  :PROPERTIES:" org-content)
        (push (format "  :COLLECTION_ID: %s" collection-id) org-content)
        (when library-id
          (push (format "  :LIBRARY_ID: %s" library-id) org-content))
        (push (format "  :TOTAL_ITEMS: %d" items-count) org-content)
        (push (format "  :ITEMS_WITH_ANNOTATIONS: %d" items-with-annotations) org-content)
        (push "  :END:" org-content)
        (push "" org-content)

        (if (null items)
            (progn
              (push "No items with annotations found in this collection." org-content)
              (push "" org-content))

          ;; Process each item with annotations
          (dolist (item-data items)
            ;; Get citation key for org-cite format
            (let* ((item-id (cdr (assq 'item-id item-data)))
                   (citation-key (zotero-get-citation-key-for-item item-id library-id))
                   ;; Format item annotations (use existing function but at sub-level)
                   (item-org (zotero-format-as-org-mode item-data citation-key)))

              ;; Adjust heading levels (add one * to each heading)
              (dolist (line (split-string item-org "\n"))
                (if (string-prefix-p "*" line)
                    (push (concat "*" line) org-content)
                  (push line org-content)))

              (push "" org-content))))

        (mapconcat 'identity (nreverse org-content) "\n")))))

(defun zotero-format-collection-annotations-as-markdown (collection-data)
  "Format collection annotation data as markdown text.
COLLECTION-DATA should be the result from `zotero-get-all-collection-annotations'.
Returns formatted markdown string."
  (let ((error-msg (cdr (assq 'error collection-data))))
    (if error-msg
        (format "# Error: %s\n" error-msg)

      (let* ((collection-name (zotero-normalize-text-encoding (cdr (assq 'collection-name collection-data))))
             (collection-id (cdr (assq 'collection-id collection-data)))
             (library-id (cdr (assq 'library-id collection-data)))
             (items-count (cdr (assq 'items-count collection-data)))
             (items (cdr (assq 'items collection-data)))
             (items-with-annotations (length items))
             (md-content '()))

        ;; Main collection header
        (push (format "# Collection: %s" collection-name) md-content)
        (push "" md-content)
        (push (format "**Collection ID:** %s" collection-id) md-content)
        (when library-id
          (push (format "**Library ID:** %s" library-id) md-content))
        (push (format "**Total Items:** %d" items-count) md-content)
        (push (format "**Items with Annotations:** %d" items-with-annotations) md-content)
        (push "" md-content)

        (if (null items)
            (progn
              (push "No items with annotations found in this collection." md-content)
              (push "" md-content))

          ;; Process each item with annotations
          (dolist (item-data items)
            ;; Get citation key for citations
            (let* ((item-id (cdr (assq 'item-id item-data)))
                   (citation-key (zotero-get-citation-key-for-item item-id library-id))
                   ;; Format item annotations (use existing function but at sub-level)
                   (item-md (zotero-format-as-markdown item-data citation-key)))

              ;; Adjust heading levels (add one # to each heading)
              (dolist (line (split-string item-md "\n"))
                (if (string-prefix-p "#" line)
                    (push (concat "#" line) md-content)
                  (push line md-content)))

              (push "" md-content))))

        (mapconcat 'identity (nreverse md-content) "\n")))))

;;; CLI delegation

(defun zotero-get-annotations-via-cli (item-id &optional format)
  "Get annotations for ITEM-ID by delegating to the Python CLI.
FORMAT is either \"org\" or \"markdown\" (default \"org\").
Requires `zotero-cli-directory' to be set.
Returns the formatted string, or nil on failure."
  (unless zotero-cli-directory
    (error "Set `zotero-cli-directory' to use CLI delegation"))
  (let* ((fmt (or format "org"))
         (flag (pcase fmt
                 ("org" "--org")
                 ("markdown" "--markdown")
                 (_ (error "Unknown format: %s" fmt))))
         (cmd (format "uv run --directory %s zotero-get-annots %s %s --stdout"
                      (shell-quote-argument
                       (expand-file-name zotero-cli-directory))
                      (shell-quote-argument item-id)
                      flag))
         (output (shell-command-to-string cmd)))
    (when (and output (not (string-empty-p (string-trim output))))
      (string-trim output))))

(provide 'zotero-api)

;;; zotero-api.el ends here
