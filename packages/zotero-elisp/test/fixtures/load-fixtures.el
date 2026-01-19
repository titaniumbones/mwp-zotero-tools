;;; load-fixtures.el --- Load JSON fixtures for testing -*- lexical-binding: t; -*-

;;; Commentary:
;; Helper functions to load shared JSON fixtures for testing.

;;; Code:

(require 'json)

(defvar zotero-test-fixtures-dir
  (expand-file-name "../../../../shared/fixtures"
                    (file-name-directory (or load-file-name buffer-file-name)))
  "Path to shared fixtures directory.")

(defun zotero-test-load-fixture (path)
  "Load JSON fixture from PATH relative to shared/fixtures."
  (let ((full-path (expand-file-name path zotero-test-fixtures-dir)))
    (with-temp-buffer
      (insert-file-contents full-path)
      (json-read))))

(defun zotero-test-fixture-journal-article ()
  "Load journal article fixture."
  (zotero-test-load-fixture "items/journal-article.json"))

(defun zotero-test-fixture-book ()
  "Load book fixture."
  (zotero-test-load-fixture "items/book.json"))

(defun zotero-test-fixture-item-with-children ()
  "Load item with children fixture."
  (zotero-test-load-fixture "items/item-with-children.json"))

(defun zotero-test-fixture-nested-collections ()
  "Load nested collections fixture."
  (zotero-test-load-fixture "collections/nested-collections.json"))

(defun zotero-test-fixture-flat-collections ()
  "Load flat collections fixture."
  (zotero-test-load-fixture "collections/flat-collections.json"))

(defun zotero-test-fixture-pdf-annotations ()
  "Load PDF annotations fixture."
  (zotero-test-load-fixture "annotations/pdf-highlights.json"))

(defun zotero-test-fixture-group-libraries ()
  "Load group libraries fixture."
  (zotero-test-load-fixture "libraries/group-libraries.json"))

(provide 'load-fixtures)

;;; load-fixtures.el ends here
