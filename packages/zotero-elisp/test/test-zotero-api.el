;;; test-zotero-api.el --- Unit tests for zotero-api -*- lexical-binding: t; -*-

;;; Commentary:
;; Unit tests for zotero-api.el functionality.
;; Uses cl-letf to mock zotero--make-request for testing without a running Zotero instance.

;;; Code:

(require 'ert)
(require 'cl-lib)

;; Add load paths
(add-to-list 'load-path (file-name-directory (or load-file-name buffer-file-name)))
(add-to-list 'load-path (expand-file-name ".." (file-name-directory (or load-file-name buffer-file-name))))
(add-to-list 'load-path (expand-file-name "fixtures" (file-name-directory (or load-file-name buffer-file-name))))

(require 'zotero-api)
(require 'load-fixtures)

;;; Helper macros for mocking

(defmacro with-zotero-mock-request (endpoint-responses &rest body)
  "Execute BODY with zotero--make-request mocked.
ENDPOINT-RESPONSES is an alist mapping endpoints to responses."
  (declare (indent 1))
  `(cl-letf (((symbol-function 'zotero--make-request)
              (lambda (endpoint &optional callback)
                (let ((response (cdr (assoc endpoint ,endpoint-responses))))
                  (if callback
                      (funcall callback response)
                    response)))))
     ,@body))

;;; Tests for zotero-get-item

(ert-deftest test-zotero-get-item-personal-library ()
  "Test getting item from personal library."
  (let ((article (zotero-test-fixture-journal-article)))
    (with-zotero-mock-request `(("/users/0/items/ABC12345" . ,article))
                              (let ((result (zotero-get-item "ABC12345")))
                                (should result)
                                (should (string= (cdr (assq 'key result)) "ABC12345"))))))

(ert-deftest test-zotero-get-item-group-library ()
  "Test getting item from group library."
  (let ((article (zotero-test-fixture-journal-article)))
    (with-zotero-mock-request `(("/groups/12345/items/ABC12345" . ,article))
                              (let ((result (zotero-get-item "ABC12345" "12345")))
                                (should result)
                                (should (string= (cdr (assq 'key result)) "ABC12345"))))))

(ert-deftest test-zotero-get-item-not-found ()
  "Test getting non-existent item."
  (with-zotero-mock-request '(("/users/0/items/NOTFOUND" . nil))
                            (let ((result (zotero-get-item "NOTFOUND")))
                              (should-not result))))

;;; Tests for zotero-get-item-children

(ert-deftest test-zotero-get-item-children-returns-list ()
  "Test that get-item-children returns a list."
  (let* ((fixture (zotero-test-fixture-item-with-children))
         (children (cdr (assq 'children fixture))))
    (with-zotero-mock-request `(("/users/0/items/PARENT01/children" . ,children))
                              (let ((result (zotero-get-item-children "PARENT01")))
                                (should (listp result))
                                (should (= (length result) 3))))))

(ert-deftest test-zotero-get-item-children-empty ()
  "Test getting children when none exist."
  (with-zotero-mock-request '(("/users/0/items/ABC123/children" . []))
                            (let ((result (zotero-get-item-children "ABC123")))
                              (should (listp result))
                              (should (= (length result) 0)))))

;;; Tests for zotero-get-collections

(ert-deftest test-zotero-get-collections ()
  "Test getting collections from personal library."
  (let ((collections (zotero-test-fixture-nested-collections)))
    (with-zotero-mock-request `(("/users/0/collections" . ,collections))
                              (let ((result (zotero-get-collections)))
                                (should (listp result))
                                (should (= (length result) 5))))))

(ert-deftest test-zotero-get-collections-group-library ()
  "Test getting collections from group library."
  (let ((collections (zotero-test-fixture-flat-collections)))
    (with-zotero-mock-request `(("/groups/12345/collections" . ,collections))
                              (let ((result (zotero-get-collections "12345")))
                                (should (listp result))
                                (should (= (length result) 3))))))

(ert-deftest test-zotero-get-collections-empty ()
  "Test getting collections when none exist."
  (with-zotero-mock-request '(("/users/0/collections" . []))
                            (let ((result (zotero-get-collections)))
                              (should (listp result))
                              (should (= (length result) 0)))))

;;; Tests for zotero-get-libraries

(ert-deftest test-zotero-get-libraries ()
  "Test getting group libraries."
  (let* ((fixture (zotero-test-fixture-group-libraries))
         (groups (cdr (assq 'groups fixture))))
    (with-zotero-mock-request `(("/users/0/groups" . ,groups))
                              (let ((result (zotero-get-libraries)))
                                (should (listp result))
                                (should (= (length result) 2))))))

(ert-deftest test-zotero-get-libraries-empty ()
  "Test getting libraries when none exist."
  (with-zotero-mock-request '(("/users/0/groups" . []))
                            (let ((result (zotero-get-libraries)))
                              (should (listp result))
                              (should (= (length result) 0)))))

;;; Tests for zotero-get-pdf-attachments

(ert-deftest test-zotero-get-pdf-attachments ()
  "Test filtering PDF attachments from children."
  (let* ((fixture (zotero-test-fixture-item-with-children))
         (children (cdr (assq 'children fixture))))
    (with-zotero-mock-request `(("/users/0/items/PARENT01/children" . ,children))
                              (let ((result (zotero-get-pdf-attachments "PARENT01")))
                                ;; Should only include the PDF attachment, not the note or URL
                                (should (= (length result) 1))
                                (let* ((pdf (car result))
                                       (data (cdr (assq 'data pdf))))
                                  (should (string= (cdr (assq 'contentType data)) "application/pdf")))))))

(ert-deftest test-zotero-get-pdf-attachments-none ()
  "Test when no PDF attachments exist."
  (let ((children [((data . ((itemType . "note")))
                    (key . "NOTE001"))]))
    (with-zotero-mock-request `(("/users/0/items/ABC123/children" . ,children))
                              (let ((result (zotero-get-pdf-attachments "ABC123")))
                                (should (= (length result) 0))))))

;;; Tests for zotero-get-items

(ert-deftest test-zotero-get-items-with-limit ()
  "Test getting items with limit."
  (let ((article (zotero-test-fixture-journal-article))
        (book (zotero-test-fixture-book)))
    (with-zotero-mock-request `(("/users/0/items?limit=10" . ,(vector article book)))
                              (let ((result (zotero-get-items nil 10)))
                                (should (listp result))
                                (should (= (length result) 2))))))

(ert-deftest test-zotero-get-items-with-type-filter ()
  "Test getting items with type filter."
  (let ((article (zotero-test-fixture-journal-article)))
    (with-zotero-mock-request `(("/users/0/items?limit=25&itemType=journalArticle" . ,(vector article)))
                              (let ((result (zotero-get-items nil nil "journalArticle")))
                                (should (listp result))
                                (should (= (length result) 1))))))

;;; Tests for zotero-get-attachment-annotations

(ert-deftest test-zotero-get-attachment-annotations ()
  "Test getting annotations for attachment."
  (let ((annotations (zotero-test-fixture-pdf-annotations)))
    (with-zotero-mock-request `(("/users/0/items/ATTACH01/children" . ,annotations))
                              (let ((result (zotero-get-attachment-annotations "ATTACH01")))
                                (should (listp result))
                                (should (= (length result) 5))))))

(ert-deftest test-zotero-get-attachment-annotations-empty ()
  "Test getting annotations when none exist."
  (with-zotero-mock-request '(("/users/0/items/ATTACH01/children" . [])
                              ("/users/0/items?limit=1000&itemType=annotation" . []))
                            (let ((result (zotero-get-attachment-annotations "ATTACH01")))
                              (should (listp result))
                              (should (= (length result) 0)))))

;;; Tests for zotero-get-file-attachments

(ert-deftest test-zotero-get-file-attachments-pdf-and-epub ()
  "Test that file attachments returns both PDF and EPUB."
  (let ((children [((data . ((itemType . "attachment")
                             (contentType . "application/pdf")))
                    (key . "PDF001"))
                   ((data . ((itemType . "attachment")
                             (contentType . "application/epub+zip")))
                    (key . "EPUB01"))
                   ((data . ((itemType . "note")))
                    (key . "NOTE01"))]))
    (with-zotero-mock-request `(("/users/0/items/ITEM01/children" . ,children))
                              (let ((result (zotero-get-file-attachments "ITEM01")))
                                (should (= (length result) 2))))))

(ert-deftest test-zotero-get-file-attachments-pdf-only ()
  "Test filtering to PDF only via content-types arg."
  (let ((children [((data . ((itemType . "attachment")
                             (contentType . "application/pdf")))
                    (key . "PDF001"))
                   ((data . ((itemType . "attachment")
                             (contentType . "application/epub+zip")))
                    (key . "EPUB01"))]))
    (with-zotero-mock-request `(("/users/0/items/ITEM01/children" . ,children))
                              (let ((result (zotero-get-file-attachments "ITEM01" nil '("application/pdf"))))
                                (should (= (length result) 1))
                                (should (string= (cdr (assq 'key (car result))) "PDF001"))))))

;;; Tests for zotero-sort-annotations

(ert-deftest test-zotero-sort-annotations-by-sort-index ()
  "Test sorting annotations by annotationSortIndex."
  (let ((annotations
         (list '((data . ((annotationSortIndex . "00020|004000|00150"))))
               '((data . ((annotationSortIndex . "00005|001234|00100"))))
               '((data . ((annotationSortIndex . "00012|002345|00200")))))))
    (let ((sorted (zotero-sort-annotations annotations)))
      (should (string= (cdr (assq 'annotationSortIndex (cdr (assq 'data (nth 0 sorted)))))
                       "00005|001234|00100"))
      (should (string= (cdr (assq 'annotationSortIndex (cdr (assq 'data (nth 1 sorted)))))
                       "00012|002345|00200"))
      (should (string= (cdr (assq 'annotationSortIndex (cdr (assq 'data (nth 2 sorted)))))
                       "00020|004000|00150")))))

(ert-deftest test-zotero-sort-annotations-fallback-to-page ()
  "Test sort fallback to page label when no sort index."
  (let ((annotations
         (list '((data . ((annotationPageLabel . "20"))))
               '((data . ((annotationPageLabel . "5")))))))
    (let ((sorted (zotero-sort-annotations annotations)))
      (should (string= (cdr (assq 'annotationPageLabel (cdr (assq 'data (nth 0 sorted)))))
                       "5"))
      (should (string= (cdr (assq 'annotationPageLabel (cdr (assq 'data (nth 1 sorted)))))
                       "20")))))

;;; Tests for helper functions

(ert-deftest test-zotero--is-spine-index ()
  "Test EPUB spine index detection."
  (should (zotero--is-spine-index "00055"))
  (should (zotero--is-spine-index "00003"))
  (should-not (zotero--is-spine-index "5"))
  (should-not (zotero--is-spine-index "12"))
  (should-not (zotero--is-spine-index ""))
  (should-not (zotero--is-spine-index nil)))

(ert-deftest test-zotero--build-open-pdf-link ()
  "Test building zotero://open-pdf links."
  (should (string= (zotero--build-open-pdf-link "ATT001" "5" "ANN001")
                   "zotero://open-pdf/library/items/ATT001?page=5&annotation=ANN001"))
  (should (string= (zotero--build-open-pdf-link "ATT001" "" "ANN001")
                   "zotero://open-pdf/library/items/ATT001?annotation=ANN001"))
  (should (string= (zotero--build-open-pdf-link "ATT001" "" "")
                   "zotero://open-pdf/library/items/ATT001")))

(ert-deftest test-zotero--page-display ()
  "Test page display text computation."
  (should (string= (zotero--page-display "5" "") "p. 5"))
  (should (string= (zotero--page-display "" "00003|001000|00050") "annotation"))
  (should (string= (zotero--page-display "" "") "p. ?"))
  (should (string= (zotero--page-display "00055" "") "annotation")))

;;; Tests for per-annotation org formatting

(ert-deftest test-zotero-format-org-highlight ()
  "Test org formatting of a highlight annotation."
  (let ((annotation '((data . ((annotationType . "highlight")
                               (key . "ANN001")
                               (annotationText . "Some highlighted text")
                               (annotationComment . "My comment")
                               (annotationPageLabel . "5")
                               (annotationSortIndex . "00005|001234|00100")
                               (tags . (((tag . "important")))))))))
    (let ((lines (zotero--format-single-annotation-org annotation "ATT001" "smith2023")))
      (should (member "[[zotero://open-pdf/library/items/ATT001?page=5&annotation=ANN001][p. 5]]:" lines))
      (should (member "#+begin_quote" lines))
      (should (member "Some highlighted text" lines))
      (should (member "#+end_quote" lines))
      (should (member "My comment" lines))
      (should (member "[cite:@smith2023, p.5]" lines))
      (should (member ":important:" lines)))))

(ert-deftest test-zotero-format-org-note ()
  "Test org formatting of a note annotation."
  (let ((annotation '((data . ((annotationType . "note")
                               (key . "ANN002")
                               (annotationText . "")
                               (annotationComment . "A note comment")
                               (annotationPageLabel . "10")
                               (annotationSortIndex . "00010|002000|00050")
                               (tags . ()))))))
    (let ((lines (zotero--format-single-annotation-org annotation "ATT001")))
      (should (member "#+begin_comment" lines))
      (should (member "A note comment" lines))
      (should (member "#+end_comment" lines)))))

(ert-deftest test-zotero-format-org-image ()
  "Test org formatting of an image annotation."
  (let ((annotation '((data . ((annotationType . "image")
                               (key . "ANN003")
                               (annotationText . "")
                               (annotationComment . "Figure 1 caption")
                               (annotationPageLabel . "8")
                               (annotationSortIndex . "00008|001800|00300")
                               (tags . (((tag . "figure")))))))))
    (let ((lines (zotero--format-single-annotation-org annotation "ATT001")))
      (should (member "#+begin_example" lines))
      (should (member "[Image annotation]" lines))
      (should (member "#+end_example" lines))
      (should (member "Figure 1 caption" lines))
      (should (member ":figure:" lines)))))

(ert-deftest test-zotero-format-org-epub-annotation ()
  "Test org formatting of an EPUB annotation shows 'annotation' not 'p. ?'."
  (let ((annotation '((data . ((annotationType . "highlight")
                               (key . "EPANN01")
                               (annotationText . "EPUB text")
                               (annotationComment . "")
                               (annotationPageLabel . "")
                               (annotationSortIndex . "00003|001000|00050")
                               (tags . ()))))))
    (let ((lines (zotero--format-single-annotation-org annotation "EPATT01")))
      (should (member "[[zotero://open-pdf/library/items/EPATT01?annotation=EPANN01][annotation]]:" lines)))))

;;; Tests for full format-as-org-mode

(ert-deftest test-zotero-format-as-org-mode-custom-id ()
  "Test that CUSTOM_ID is emitted when citation-key is provided."
  (let ((data '((item-title . "Test Article")
                (item-type . "journalArticle")
                (item-id . "ABC123")
                (attachments . (((attachment-title . "test.pdf")
                                 (attachment-id . "ATT001")
                                 (annotations . ())))))))
    (let ((result (zotero-format-as-org-mode data "smith2023")))
      (should (string-match-p ":CUSTOM_ID: smith2023" result)))))

(ert-deftest test-zotero-format-as-org-mode-single-attachment-no-header ()
  "Test that single attachment mode skips attachment header."
  (let ((data '((item-title . "Test Article")
                (item-type . "journalArticle")
                (item-id . "ABC123")
                (attachments . (((attachment-title . "test.pdf")
                                 (attachment-id . "ATT001")
                                 (annotations . ())))))))
    (let ((result (zotero-format-as-org-mode data)))
      (should-not (string-match-p "\\*\\* test\\.pdf" result)))))

(ert-deftest test-zotero-format-as-org-mode-multi-attachment-headers ()
  "Test that multi-attachment mode includes attachment headers."
  (let ((data '((item-title . "Test Article")
                (item-type . "journalArticle")
                (item-id . "ABC123")
                (attachments . (((attachment-title . "first.pdf")
                                 (attachment-id . "ATT001")
                                 (annotations . ()))
                                ((attachment-title . "second.pdf")
                                 (attachment-id . "ATT002")
                                 (annotations . ())))))))
    (let ((result (zotero-format-as-org-mode data)))
      (should (string-match-p "\\*\\* first\\.pdf" result))
      (should (string-match-p "\\*\\* second\\.pdf" result)))))

(ert-deftest test-zotero-format-as-org-mode-per-annotation-blocks ()
  "Test that each annotation gets its own block."
  (let ((data `((item-title . "Test Article")
                (item-type . "journalArticle")
                (item-id . "ABC123")
                (attachments . (((attachment-title . "test.pdf")
                                 (attachment-id . "ATT001")
                                 (annotations . (((data . ((annotationType . "highlight")
                                                           (key . "A01")
                                                           (annotationText . "First highlight")
                                                           (annotationComment . "")
                                                           (annotationPageLabel . "1")
                                                           (annotationSortIndex . "00001|000100|00050")
                                                           (tags . ()))))
                                                 ((data . ((annotationType . "highlight")
                                                           (key . "A02")
                                                           (annotationText . "Second highlight")
                                                           (annotationComment . "")
                                                           (annotationPageLabel . "2")
                                                           (annotationSortIndex . "00002|000200|00050")
                                                           (tags . ()))))))))))))
    (let ((result (zotero-format-as-org-mode data)))
      ;; Should have two separate begin_quote blocks
      (let ((count 0) (start 0))
        (while (string-match "#\\+begin_quote" result start)
          (setq count (1+ count))
          (setq start (match-end 0)))
        (should (= 2 count))))))

;;; Tests for per-annotation markdown formatting

(ert-deftest test-zotero-format-md-highlight ()
  "Test markdown formatting of a highlight annotation."
  (let ((annotation '((data . ((annotationType . "highlight")
                               (key . "ANN001")
                               (annotationText . "Some highlighted text")
                               (annotationComment . "My comment")
                               (annotationPageLabel . "5")
                               (annotationSortIndex . "00005|001234|00100")
                               (tags . (((tag . "important")) ((tag . "key")))))))))
    (let ((lines (zotero--format-single-annotation-md annotation "ATT001" "smith2023")))
      (should (member "[p. 5](zotero://open-pdf/library/items/ATT001?page=5&annotation=ANN001):" lines))
      (should (member "> Some highlighted text" lines))
      (should (member "My comment" lines))
      (should (member "[cite:@smith2023, p.5]" lines))
      (should (cl-find-if (lambda (l) (string-match-p "Tags:.*`important`.*`key`" l)) lines)))))

(ert-deftest test-zotero-format-md-note ()
  "Test markdown formatting of a note annotation."
  (let ((annotation '((data . ((annotationType . "note")
                               (key . "ANN002")
                               (annotationText . "")
                               (annotationComment . "A note comment")
                               (annotationPageLabel . "10")
                               (annotationSortIndex . "00010|002000|00050")
                               (tags . ()))))))
    (let ((lines (zotero--format-single-annotation-md annotation "ATT001")))
      (should (member "*A note comment*" lines)))))

(ert-deftest test-zotero-format-md-image ()
  "Test markdown formatting of an image annotation."
  (let ((annotation '((data . ((annotationType . "image")
                               (key . "ANN003")
                               (annotationText . "")
                               (annotationComment . "Figure caption")
                               (annotationPageLabel . "8")
                               (annotationSortIndex . "00008|001800|00300")
                               (tags . ()))))))
    (let ((lines (zotero--format-single-annotation-md annotation "ATT001")))
      (should (member "`[Image annotation]`" lines))
      (should (member "Figure caption" lines)))))

(ert-deftest test-zotero-format-as-markdown-citation-key ()
  "Test that Citation Key is emitted in markdown header."
  (let ((data '((item-title . "Test Article")
                (item-type . "journalArticle")
                (item-id . "ABC123")
                (attachments . ()))))
    (let ((result (zotero-format-as-markdown data "smith2023")))
      (should (string-match-p "\\*\\*Citation Key:\\*\\* smith2023" result)))))

;;; Tests for normalize-text-encoding

(ert-deftest test-zotero-normalize-text-encoding-nil ()
  "Test that nil input returns nil."
  (should (null (zotero-normalize-text-encoding nil))))

(ert-deftest test-zotero-normalize-text-encoding-empty ()
  "Test that empty string returns empty string."
  (should (string= (zotero-normalize-text-encoding "") "")))

(ert-deftest test-zotero-normalize-text-encoding-plain ()
  "Test that plain text is unchanged."
  (let ((text "This is plain ASCII text."))
    (should (string= (zotero-normalize-text-encoding text) text))))

(ert-deftest test-zotero-normalize-text-encoding-valid-unicode ()
  "Test that valid Unicode is preserved."
  (let ((text "Already valid: e n u (c) deg +/-"))
    (should (string= (zotero-normalize-text-encoding text) text))))

;;; Tests for BBT integration

(ert-deftest test-zotero--bbt-available-p-caches-result ()
  "Test that BBT availability is cached."
  (let ((zotero--bbt-available 'unavailable))
    (should-not (zotero--bbt-available-p)))
  (let ((zotero--bbt-available t))
    (should (zotero--bbt-available-p))))

(ert-deftest test-zotero--bbt-get-citation-key-constructs-key ()
  "Test that BBT citation key uses correct library:item format."
  (let ((called-with nil))
    (cl-letf (((symbol-function 'zotero--bbt-json-rpc)
               (lambda (method params)
                 (setq called-with (list method params))
                 '(("1:ABC123" . "smith2023")))))
      (let ((result (zotero--bbt-get-citation-key "ABC123")))
        (should (string= result "smith2023"))
        (should (string= (car called-with) "item.citationkey"))))))

(ert-deftest test-zotero--bbt-get-citation-key-custom-library ()
  "Test BBT citation key with custom library ID."
  (cl-letf (((symbol-function 'zotero--bbt-json-rpc)
             (lambda (_method _params)
               '(("42:ITEM01" . "jones2024")))))
    (should (string= (zotero--bbt-get-citation-key "ITEM01" "42")
                     "jones2024"))))

(ert-deftest test-zotero-get-citation-key-tries-bbt-first ()
  "Test that citation key lookup tries BBT before BibTeX export."
  (let ((zotero--bbt-available t)
        (bbt-called nil)
        (bibtex-called nil))
    (cl-letf (((symbol-function 'zotero--bbt-get-citation-key)
               (lambda (_id &optional _lib)
                 (setq bbt-called t)
                 "bbt-key"))
              ((symbol-function 'zotero-export-item-bibtex)
               (lambda (_id &optional _lib)
                 (setq bibtex-called t)
                 nil)))
      (let ((result (zotero-get-citation-key-for-item "TEST01")))
        (should (string= result "bbt-key"))
        (should bbt-called)
        (should-not bibtex-called)))))

(ert-deftest test-zotero-get-citation-key-falls-back-to-bibtex ()
  "Test that citation key falls back to BibTeX when BBT unavailable."
  (let ((zotero--bbt-available 'unavailable))
    (cl-letf (((symbol-function 'zotero-export-item-bibtex)
               (lambda (_id &optional _lib)
                 "@article{fallback2023, title={Test}}")))
      (let ((result (zotero-get-citation-key-for-item "TEST01")))
        (should (string= result "fallback2023"))))))

;;; Tests for chapter map helpers

(ert-deftest test-zotero--resolve-attachment-path ()
  "Test attachment path resolution."
  (let ((path (zotero--resolve-attachment-path "ATT001" "paper.pdf")))
    (should (string-match-p "Zotero/storage/ATT001/paper.pdf" path))))

(ert-deftest test-zotero--get-chapters-for-page-numeric ()
  "Test chapter lookup with numeric page labels."
  (let ((chapter-map '(("Introduction" "1" 1)
                       ("Background" "5" 1)
                       ("1.1 History" "6" 2)
                       ("Methods" "20" 1))))
    ;; Page 10 should be in Background > 1.1 History
    (let ((result (zotero--get-chapters-for-page chapter-map "10")))
      (should (= (length result) 2))
      (should (string= (nth 0 (nth 0 result)) "Background"))
      (should (string= (nth 0 (nth 1 result)) "1.1 History")))
    ;; Page 3 should be in Introduction only
    (let ((result (zotero--get-chapters-for-page chapter-map "3")))
      (should (= (length result) 1))
      (should (string= (nth 0 (car result)) "Introduction")))
    ;; Page 25 should be in Methods only (deeper levels cleared)
    (let ((result (zotero--get-chapters-for-page chapter-map "25")))
      (should (= (length result) 1))
      (should (string= (nth 0 (car result)) "Methods")))))

(ert-deftest test-zotero--get-chapters-for-page-empty ()
  "Test chapter lookup with empty/nil inputs."
  (should-not (zotero--get-chapters-for-page nil "5"))
  (should-not (zotero--get-chapters-for-page '(("Ch1" "1" 1)) ""))
  (should-not (zotero--get-chapters-for-page '(("Ch1" "1" 1)) nil)))

(ert-deftest test-zotero--get-chapters-for-page-before-first ()
  "Test chapter lookup for page before first chapter."
  (let ((chapter-map '(("Chapter 1" "10" 1))))
    (should-not (zotero--get-chapters-for-page chapter-map "5"))))

;;; Tests for org formatting with chapter headings

(ert-deftest test-zotero-format-org-with-chapters ()
  "Test that chapter headings appear in org output."
  (let ((zotero-cli-directory "/dummy"))
    (cl-letf (((symbol-function 'zotero--get-chapter-map-for-attachment)
               (lambda (_att-id _filename)
                 '(("Chapter 1" "1" 1) ("Section 1.1" "3" 2) ("Chapter 2" "10" 1)))))
      (let ((data `((item-title . "Test Article")
                    (item-type . "journalArticle")
                    (item-id . "ABC123")
                    (attachments . (((attachment-title . "test.pdf")
                                     (attachment-id . "ATT001")
                                     (filename . "test.pdf")
                                     (annotations . (((data . ((annotationType . "highlight")
                                                               (key . "A01")
                                                               (annotationText . "First text")
                                                               (annotationComment . "")
                                                               (annotationPageLabel . "2")
                                                               (annotationSortIndex . "00002|000100|00050")
                                                               (tags . ()))))
                                                     ((data . ((annotationType . "highlight")
                                                               (key . "A02")
                                                               (annotationText . "Second text")
                                                               (annotationComment . "")
                                                               (annotationPageLabel . "12")
                                                               (annotationSortIndex . "00012|000200|00050")
                                                               (tags . ()))))))))))))
        (let ((result (zotero-format-as-org-mode data)))
          ;; Should contain chapter headings
          (should (string-match-p "\\*\\* Chapter 1" result))
          (should (string-match-p "\\*\\* Chapter 2" result)))))))

;;; Tests for CLI delegation

(ert-deftest test-zotero-get-annotations-via-cli-requires-directory ()
  "Test that CLI delegation errors without zotero-cli-directory."
  (let ((zotero-cli-directory nil))
    (should-error (zotero-get-annotations-via-cli "ITEM01"))))

;;; Test Suite Runner

(defun zotero-api-run-tests ()
  "Run all zotero-api tests."
  (interactive)
  (ert-run-tests-batch-and-exit "test-zotero-"))

(provide 'test-zotero-api)

;;; test-zotero-api.el ends here
