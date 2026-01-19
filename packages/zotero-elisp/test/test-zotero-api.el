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

;;; Test Suite Runner

(defun zotero-api-run-tests ()
  "Run all zotero-api tests."
  (interactive)
  (ert-run-tests-batch-and-exit "test-zotero-"))

(provide 'test-zotero-api)

;;; test-zotero-api.el ends here
