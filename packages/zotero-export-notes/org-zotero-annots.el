;;; org-zotero-annots.el --- Insert Zotero annotations as org subtrees -*- lexical-binding: t -*-

;; Author: Matt Price
;; Version: 0.2.0
;; Package-Requires: ((emacs "27.1"))
;; Keywords: org, zotero, annotations, pdf
;; URL: https://github.com/titaniumbones/zotero-export-notes

;;; Commentary:

;; This package fetches PDF annotations from Zotero via the zotero-export-org-notes
;; plugin's HTTP API and inserts them as org-mode subtrees.
;;
;; Requirements:
;; - Zotero 7 with zotero-export-org-notes plugin installed
;; - Better BibTeX (recommended) for citation keys
;;
;; Optional:
;; - citar package for citation key completion from BibTeX library
;;
;; Usage:
;;   M-x org-zotero-annots-insert              ; Insert single item by citekey
;;   M-x org-zotero-annots-insert-at-point     ; Insert at point
;;   M-x org-zotero-annots-insert-collection   ; Insert all items in a collection
;;   M-x org-zotero-annots-insert-collection-at-point
;;
;; For collection commands, use C-u prefix to include subcollections recursively.
;;
;; Configuration:
;;   (setq org-zotero-annots-port 23119)  ; Zotero HTTP server port
;;   (setq org-zotero-annots-citekey-source 'auto)  ; 'auto, 'citar, 'bbt, or 'manual
;;
;; Per-file library ID (for group libraries):
;;   #+ZOTERO_LIBRARY: 123
;;   Or set via file-local variable: org-zotero-annots-library-id

;;; Code:

(require 'url)
(require 'json)
(require 'org)

;;; Customization

(defgroup org-zotero-annots nil
  "Insert Zotero annotations as org subtrees."
  :group 'org
  :prefix "org-zotero-annots-")

(defcustom org-zotero-annots-port 23119
  "Port for Zotero HTTP server.
Check Zotero preferences (Advanced > Config Editor) for
`extensions.zotero.httpServer.port' if the default doesn't work."
  :type 'integer
  :group 'org-zotero-annots)

(defcustom org-zotero-annots-citekey-source 'auto
  "Source for citation key selection.
- `auto': Use citar if available, else Zotero picker
- `citar': Always use citar (requires citar package and bibliography)
- `zotero': Use Zotero selection or manual entry
- `manual': Always prompt for manual text entry"
  :type '(choice (const :tag "Auto-detect best available" auto)
                 (const :tag "Citar (requires setup)" citar)
                 (const :tag "Zotero selection" zotero)
                 (const :tag "Manual entry" manual))
  :group 'org-zotero-annots)

(defcustom org-zotero-annots-timeout 30
  "Timeout in seconds for HTTP requests to Zotero."
  :type 'integer
  :group 'org-zotero-annots)

;;; Buffer-local Variables

(defvar-local org-zotero-annots-library-id nil
  "Zotero library ID for this buffer.
Set this for group libraries. Can be configured via:
- #+ZOTERO_LIBRARY: <id> keyword in org file
- File-local variable
- `setq-local' in your config")
(put 'org-zotero-annots-library-id 'safe-local-variable #'integerp)

;;; Internal Functions - HTTP Helpers

(defun org-zotero-annots--http-post (url data)
  "Make HTTP POST request to URL with DATA (alist).
Returns parsed JSON response or nil on error."
  (let* ((url-request-method "POST")
         (url-request-extra-headers '(("Content-Type" . "application/json")))
         (url-request-data (encode-coding-string (json-encode data) 'utf-8))
         buffer)
    (condition-case nil
        (setq buffer (url-retrieve-synchronously url nil nil org-zotero-annots-timeout))
      (error (setq buffer nil)))
    (when buffer
      (unwind-protect
          (with-current-buffer buffer
            (goto-char (point-min))
            (when (re-search-forward "^\r?\n" nil t)
              (let* ((json-object-type 'plist)
                     (json-key-type 'keyword)
                     (json-text (buffer-substring-no-properties (point) (point-max))))
                (condition-case nil
                    (json-read-from-string json-text)
                  (error nil)))))
        (kill-buffer buffer)))))

;;; Internal Functions - Library ID

(defun org-zotero-annots--get-library-id ()
  "Get the Zotero library ID for current buffer.
Checks buffer-local variable first, then #+ZOTERO_LIBRARY keyword."
  (or org-zotero-annots-library-id
      (org-zotero-annots--parse-org-keyword "ZOTERO_LIBRARY")))

(defun org-zotero-annots--parse-org-keyword (keyword)
  "Parse #+KEYWORD: value from current org buffer.
Returns the value as a string, or nil if not found."
  (save-excursion
    (goto-char (point-min))
    (let ((case-fold-search t)
          (re (format "^#\\+%s:[ \t]+\\(.+\\)$" (regexp-quote keyword))))
      (when (re-search-forward re nil t)
        (let ((val (string-trim (match-string 1))))
          ;; Convert to number if it looks like one
          (if (string-match-p "^[0-9]+$" val)
              (string-to-number val)
            val))))))

;;; Internal Functions - Zotero Integration

(defun org-zotero-annots--zotero-available-p ()
  "Check if Zotero is available by trying the libraries endpoint."
  (let ((response (org-zotero-annots--http-post
                   (format "http://localhost:%d/export-org/libraries"
                           org-zotero-annots-port)
                   nil)))
    (and response (eq (plist-get response :success) t))))

(defun org-zotero-annots--zotero-picker ()
  "Get citekey of currently selected item in Zotero.
Focuses Zotero window and prompts user to select an item if needed."
  (let ((response (org-zotero-annots--http-post
                   (format "http://localhost:%d/export-org/picker"
                           org-zotero-annots-port)
                   nil)))
    (if (and response (eq (plist-get response :success) t))
        (plist-get response :citekey)
      ;; No item selected - prompt user to select one
      (message "Select an item in Zotero, then press any key here...")
      (read-event)
      ;; Try again
      (let ((retry-response (org-zotero-annots--http-post
                             (format "http://localhost:%d/export-org/picker"
                                     org-zotero-annots-port)
                             nil)))
        (if (and retry-response (eq (plist-get retry-response :success) t))
            (plist-get retry-response :citekey)
          (user-error "No item selected: %s"
                      (or (plist-get retry-response :error) "unknown error")))))))

(defun org-zotero-annots--bbt-select-ref ()
  "Select citation key: use Zotero selection or enter manually."
  (let ((choice (completing-read
                 "Citation key: "
                 '("[Use selected item in Zotero]" "[Enter citekey manually]")
                 nil t)))
    (pcase choice
      ("[Use selected item in Zotero]" (org-zotero-annots--zotero-picker))
      ("[Enter citekey manually]" (read-string "Citation key: "))
      (_ choice))))

;;; Internal Functions - Citation Key Selection

(defun org-zotero-annots--read-citekey ()
  "Read citation key based on `org-zotero-annots-citekey-source'."
  (pcase org-zotero-annots-citekey-source
    ('manual (read-string "Citation key: "))
    ('citar
     (if (fboundp 'citar-select-ref)
         (citar-select-ref)
       (user-error "Citar not available. Set org-zotero-annots-citekey-source to 'zotero or 'auto")))
    ('zotero (org-zotero-annots--bbt-select-ref))
    ('bbt (org-zotero-annots--bbt-select-ref))  ; alias for zotero
    ('auto
     (cond
      ;; Try citar first if available
      ((fboundp 'citar-select-ref)
       (citar-select-ref))
      ;; Fall back to Zotero picker
      (t (org-zotero-annots--bbt-select-ref))))))

;;; Internal Functions - Fetch and Insert

(defun org-zotero-annots--fetch (citekey)
  "Fetch annotations for CITEKEY from Zotero API.
Returns a plist with :success, :org, :title, :count, and :error keys.
Explicitly requests org-mode format since the API now defaults to markdown."
  (let* ((library-id (org-zotero-annots--get-library-id))
         (request-data `((key . ,citekey)
                         (format . "org")  ; Explicitly request org format
                         ,@(when library-id
                             `((libraryID . ,library-id)))))
         (url (format "http://localhost:%d/export-org/citekey" org-zotero-annots-port))
         (response (org-zotero-annots--http-post url request-data)))
    (if response
        (if (eq (plist-get response :success) t)
            (list :success t
                  :org (or (plist-get response :org)
                           (plist-get response :content))
                  :title (plist-get response :title)
                  :count (plist-get response :annotationCount))
          (list :success nil
                :error (or (plist-get response :error) "Unknown API error")))
      (list :success nil
            :error (format "Connection failed (port %d). Is Zotero running?"
                           org-zotero-annots-port)))))

(defun org-zotero-annots--adjust-heading-level (org-text target-level)
  "Adjust heading levels in ORG-TEXT to start at TARGET-LEVEL.
If TARGET-LEVEL is 0 or nil, return ORG-TEXT unchanged.
Otherwise, shift all headings so the top-level becomes TARGET-LEVEL."
  (if (or (null target-level) (zerop target-level))
      org-text
    ;; The org text starts with "* Title" (level 1)
    ;; We need to shift to target-level
    (let ((shift (1- target-level)))  ; How many stars to add
      (if (zerop shift)
          org-text
        (with-temp-buffer
          (insert org-text)
          (goto-char (point-min))
          (while (re-search-forward "^\\(\\*+\\)" nil t)
            (let* ((stars (match-string 1))
                   (new-stars (make-string (+ (length stars) shift) ?*)))
              (replace-match new-stars nil nil nil 1)))
          (buffer-string))))))

(defun org-zotero-annots--current-level ()
  "Return the current org heading level, or 0 if not in a heading."
  (or (org-current-level) 0))

(defun org-zotero-annots--insert-content (citekey at-point)
  "Insert annotations for CITEKEY.
If AT-POINT is non-nil, insert at point.
Otherwise, insert at end of current subtree."
  (let ((result (org-zotero-annots--fetch citekey)))
    (if (plist-get result :success)
        (let* ((current-level (org-zotero-annots--current-level))
               (target-level (if (zerop current-level) 1 (1+ current-level)))
               (adjusted-org (org-zotero-annots--adjust-heading-level
                              (plist-get result :org)
                              target-level)))
          ;; Position cursor
          (unless at-point
            (if (zerop current-level)
                (goto-char (point-max))
              (org-end-of-subtree t t)))
          ;; Ensure we're on a new line
          (unless (bolp) (insert "\n"))
          ;; Insert the content
          (insert adjusted-org)
          (unless (bolp) (insert "\n"))
          ;; Report success
          (message "Inserted %d annotations for \"%s\""
                   (plist-get result :count)
                   (plist-get result :title)))
      ;; Report error
      (user-error "Failed to fetch annotations: %s" (plist-get result :error)))))

;;; Internal Functions - Collection Support

(defun org-zotero-annots--fetch-collections-for-library (library-id)
  "Fetch list of collections for LIBRARY-ID.
Returns list of plists with :key, :name, :parentKey, :libraryID keys."
  (let* ((request-data `((libraryID . ,library-id)))
         (response (org-zotero-annots--http-post
                    (format "http://localhost:%d/export-org/collections"
                            org-zotero-annots-port)
                    request-data)))
    (when (and response (eq (plist-get response :success) t))
      (mapcar (lambda (col)
                (list :key (plist-get col :key)
                      :name (plist-get col :name)
                      :parentKey (plist-get col :parentKey)
                      :libraryID library-id))
              (plist-get response :collections)))))

(defun org-zotero-annots--fetch-all-collections ()
  "Fetch collections from all Zotero libraries (personal and groups).
Returns list of plists with :key, :name, :parentKey, :libraryID, :libraryName keys."
  (let ((libraries (org-zotero-annots--fetch-libraries))
        (all-collections nil))
    (dolist (lib libraries)
      (let* ((lib-id (plist-get lib :id))
             (lib-name (plist-get lib :name))
             (collections (org-zotero-annots--fetch-collections-for-library lib-id)))
        (dolist (col collections)
          (push (plist-put (copy-sequence col) :libraryName lib-name)
                all-collections))))
    (nreverse all-collections)))

(defun org-zotero-annots--build-collection-path (collections col)
  "Build full path for COL using COLLECTIONS list.
Returns a string like \"Parent / Child / Grandchild\"."
  (let ((name (plist-get col :name))
        (parent-key (plist-get col :parentKey))
        (library-id (plist-get col :libraryID)))
    (if parent-key
        (let ((parent (seq-find (lambda (c)
                                  (and (equal (plist-get c :key) parent-key)
                                       (equal (plist-get c :libraryID) library-id)))
                                collections)))
          (if parent
              (concat (org-zotero-annots--build-collection-path collections parent)
                      " / " name)
            name))
      name)))

(defun org-zotero-annots--select-collection ()
  "Interactively select a Zotero collection from all libraries.
Returns a plist with :key and :libraryID."
  (let* ((collections (org-zotero-annots--fetch-all-collections))
         (candidates (mapcar (lambda (col)
                               (let ((lib-name (plist-get col :libraryName))
                                     (col-path (org-zotero-annots--build-collection-path collections col)))
                                 (cons (format "%s: %s" lib-name col-path)
                                       (list :key (plist-get col :key)
                                             :libraryID (plist-get col :libraryID)))))
                             collections)))
    (if candidates
        (let ((selection (completing-read "Select collection: "
                                          (sort candidates (lambda (a b) (string< (car a) (car b))))
                                          nil t)))
          (cdr (assoc selection candidates)))
      (user-error "No collections found. Is Zotero running?"))))

(defun org-zotero-annots--fetch-collection (collection-key library-id &optional recursive)
  "Fetch annotations for COLLECTION-KEY in LIBRARY-ID from Zotero API.
If RECURSIVE is non-nil, include subcollections.
Returns a plist with :success, :org, :collectionName, :count, :items, and :error keys."
  (let* ((request-data `((collectionKey . ,collection-key)
                         (format . "org")
                         (recursive . ,(if recursive t :json-false))
                         (libraryID . ,library-id)))
         (url (format "http://localhost:%d/export-org/collection" org-zotero-annots-port))
         (response (org-zotero-annots--http-post url request-data)))
    (if response
        (if (eq (plist-get response :success) t)
            (list :success t
                  :org (or (plist-get response :org)
                           (plist-get response :content))
                  :collectionName (plist-get response :collectionName)
                  :count (plist-get response :totalAnnotations)
                  :itemCount (plist-get response :itemCount)
                  :items (plist-get response :items))
          (list :success nil
                :error (or (plist-get response :error) "Unknown API error")))
      (list :success nil
            :error (format "Connection failed (port %d). Is Zotero running?"
                           org-zotero-annots-port)))))

(defun org-zotero-annots--insert-collection-content (collection-info recursive at-point)
  "Insert annotations for collection specified by COLLECTION-INFO plist.
COLLECTION-INFO should have :key and :libraryID.
If RECURSIVE is non-nil, include subcollections.
If AT-POINT is non-nil, insert at point.
Otherwise, insert at end of current subtree."
  (let* ((collection-key (plist-get collection-info :key))
         (library-id (plist-get collection-info :libraryID))
         (result (org-zotero-annots--fetch-collection collection-key library-id recursive)))
    (if (plist-get result :success)
        (let* ((current-level (org-zotero-annots--current-level))
               (target-level (if (zerop current-level) 1 (1+ current-level)))
               (adjusted-org (org-zotero-annots--adjust-heading-level
                              (plist-get result :org)
                              target-level)))
          ;; Position cursor
          (unless at-point
            (if (zerop current-level)
                (goto-char (point-max))
              (org-end-of-subtree t t)))
          ;; Ensure we're on a new line
          (unless (bolp) (insert "\n"))
          ;; Insert the content
          (insert adjusted-org)
          (unless (bolp) (insert "\n"))
          ;; Report success
          (message "Inserted %d annotations from %d items in \"%s\""
                   (plist-get result :count)
                   (plist-get result :itemCount)
                   (plist-get result :collectionName)))
      ;; Report error
      (user-error "Failed to fetch collection annotations: %s" (plist-get result :error)))))

;;; Internal Functions - Library Selection

(defun org-zotero-annots--fetch-libraries ()
  "Fetch list of available Zotero libraries.
Returns list of plists with :id, :name, :type keys."
  (let ((response (org-zotero-annots--http-post
                   (format "http://localhost:%d/export-org/libraries"
                           org-zotero-annots-port)
                   nil)))
    (when (and response (eq (plist-get response :success) t))
      (mapcar (lambda (lib)
                (list :id (plist-get lib :id)
                      :name (plist-get lib :name)
                      :type (plist-get lib :type)))
              (plist-get response :libraries)))))

(defun org-zotero-annots--select-library ()
  "Interactively select a Zotero library.
Returns the library ID as an integer."
  (let* ((libraries (org-zotero-annots--fetch-libraries))
         (candidates (mapcar (lambda (lib)
                               (cons (format "%s (%s, id: %d)"
                                             (plist-get lib :name)
                                             (plist-get lib :type)
                                             (plist-get lib :id))
                                     (plist-get lib :id)))
                             libraries)))
    (if candidates
        (let ((selection (completing-read "Select library: " candidates nil t)))
          (cdr (assoc selection candidates)))
      (user-error "No libraries found. Is Zotero running?"))))

;;; Interactive Commands

;;;###autoload
(defun org-zotero-annots-set-library ()
  "Set the Zotero library ID for the current buffer.
Queries Zotero for available libraries and lets you choose one.
Updates #+ZOTERO_LIBRARY: keyword in the file, or adds it to front matter."
  (interactive)
  (let ((lib-id (org-zotero-annots--select-library)))
    ;; Set buffer-local variable
    (setq-local org-zotero-annots-library-id lib-id)
    ;; Update or insert the keyword in the file
    (save-excursion
      (goto-char (point-min))
      (if (re-search-forward "^#\\+ZOTERO_LIBRARY:.*$" nil t)
          ;; Update existing keyword
          (replace-match (format "#+ZOTERO_LIBRARY: %d" lib-id))
        ;; Insert in front matter (after other keywords, or at top)
        (goto-char (point-min))
        ;; Skip past existing keywords and blank lines at top
        (while (and (not (eobp))
                    (looking-at "^\\(#\\+\\|[ \t]*$\\)"))
          (forward-line 1))
        ;; Insert before first non-keyword line
        (insert (format "#+ZOTERO_LIBRARY: %d\n" lib-id))))
    (message "Set library ID to %d" lib-id)))

;;;###autoload
(defun org-zotero-annots-insert (citekey)
  "Insert Zotero annotations for CITEKEY at end of current subtree.
If not in a heading, insert at end of buffer as top-level heading.

Citation key selection method is controlled by `org-zotero-annots-citekey-source':
- `auto': Uses citar if available, else BBT search, else manual
- `citar': Uses citar completion (requires citar package)
- `bbt': Uses Better BibTeX search
- `manual': Prompts for manual entry"
  (interactive (list (org-zotero-annots--read-citekey)))
  (org-zotero-annots--insert-content citekey nil))

;;;###autoload
(defun org-zotero-annots-insert-at-point (citekey)
  "Insert Zotero annotations for CITEKEY at point.

Citation key selection method is controlled by `org-zotero-annots-citekey-source'."
  (interactive (list (org-zotero-annots--read-citekey)))
  (org-zotero-annots--insert-content citekey t))

;;;###autoload
(defun org-zotero-annots-insert-collection (collection-info &optional recursive)
  "Insert Zotero annotations for all items in a collection.
COLLECTION-INFO is a plist with :key and :libraryID from the selector.
With prefix argument, include items from subcollections recursively.

The selector shows collections from all libraries (personal and groups)
formatted as \"Library Name: Parent / Child / Collection\".

If not in a heading, insert at end of buffer as top-level heading.
If in a heading, insert at end of current subtree as child heading."
  (interactive (list (org-zotero-annots--select-collection)
                     current-prefix-arg))
  (org-zotero-annots--insert-collection-content collection-info recursive nil))

;;;###autoload
(defun org-zotero-annots-insert-collection-at-point (collection-info &optional recursive)
  "Insert Zotero annotations for all items in a collection at point.
COLLECTION-INFO is a plist with :key and :libraryID from the selector.
With prefix argument, include items from subcollections recursively.

The selector shows collections from all libraries (personal and groups)."
  (interactive (list (org-zotero-annots--select-collection)
                     current-prefix-arg))
  (org-zotero-annots--insert-collection-content collection-info recursive t))

(provide 'org-zotero-annots)
;;; org-zotero-annots.el ends here
