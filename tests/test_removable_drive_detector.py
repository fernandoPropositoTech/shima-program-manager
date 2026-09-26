"""Consulta simulada: nao exige nem acessa unidades fisicas."""

import json
import subprocess
import unittest
from unittest.mock import Mock, patch

from app import removable_drive_detector as detector


class RemovableDriveDetectorTests(unittest.TestCase):
    def detect(self, records):
        with patch.object(detector, "_query_windows", return_value=json.dumps(records)):
            return detector.detect_removable_drives()

    def test_no_drives(self):
        self.assertEqual(self.detect([]), [])

    def test_one_removable_drive(self):
        result = self.detect([{"DeviceID": "F:", "DriveType": 2,
                               "VolumeName": "DADOS", "FileSystem": "FAT32"}])
        self.assertEqual(result, [{"drive": "F:\\", "label": "DADOS", "filesystem": "FAT32"}])

    def test_multiple_letters_sorted_without_fixed_letter(self):
        result = self.detect([{"DeviceID": letter + ":", "DriveType": 2}
                              for letter in ("g", "E", "D", "F")])
        self.assertEqual([r["drive"] for r in result], ["D:\\", "E:\\", "F:\\", "G:\\"])

    def test_internal_network_and_optical_drives_excluded(self):
        self.assertEqual(self.detect([{"DeviceID": "C:", "DriveType": kind}
                                      for kind in (0, 1, 3, 4, 5, 6)]), [])

    def test_optional_metadata(self):
        for metadata in ({}, {"VolumeName": None, "FileSystem": ""}):
            with self.subTest(metadata=metadata):
                self.assertEqual(self.detect([{"DeviceID": "D:", "DriveType": 2, **metadata}]),
                                 [{"drive": "D:\\", "label": None, "filesystem": None}])

    def test_malformed_json_and_shapes(self):
        for response in ("", "not json", "null", "{}", "[1]", '[{"DriveType": "2"}]'):
            with self.subTest(response=response):
                with patch.object(detector, "_query_windows", return_value=response):
                    with self.assertRaises(detector.DriveDetectionError):
                        detector.detect_removable_drives()

    def test_invalid_removable_metadata(self):
        for record in ({"DriveType": 2}, {"DriveType": 2, "DeviceID": "../"},
                       {"DriveType": 2, "DeviceID": "D:", "VolumeName": 123}):
            with self.subTest(record=record), self.assertRaises(detector.DriveDetectionError):
                self.detect([record])

    def test_duplicate_drives_rejected(self):
        with self.assertRaises(detector.DriveDetectionError):
            self.detect([{"DeviceID": "D:", "DriveType": 2}] * 2)

    def test_query_failures_are_explicit(self):
        for error in (FileNotFoundError(), subprocess.TimeoutExpired("powershell", 20),
                      subprocess.CalledProcessError(1, "powershell")):
            with self.subTest(error=type(error).__name__):
                with patch.object(detector.sys, "platform", "win32"), \
                        patch.object(detector.subprocess, "run", side_effect=error):
                    with self.assertRaises(detector.DriveDetectionError):
                        detector.detect_removable_drives()

    def test_non_windows_is_controlled(self):
        with patch.object(detector.sys, "platform", "linux"), \
                patch.object(detector.subprocess, "run") as run:
            with self.assertRaises(detector.DriveDetectionError):
                detector.detect_removable_drives()
            run.assert_not_called()

    def test_query_contract_and_no_file_writes(self):
        with patch.object(detector.sys, "platform", "win32"), \
                patch.object(detector.subprocess, "run", return_value=Mock(stdout="[]")) as run, \
                patch("builtins.open", side_effect=AssertionError("File access forbidden")), \
                patch("pathlib.Path.open", side_effect=AssertionError("File access forbidden")):
            self.assertEqual(detector.detect_removable_drives(), [])
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["powershell.exe", "-NoProfile", "-NonInteractive",
                                   "-Command", detector._QUERY])
        self.assertNotIn("shell", kwargs)
        self.assertEqual(kwargs["timeout"], 20)
        self.assertTrue(kwargs["check"])
        self.assertIn("Get-CimInstance -ClassName Win32_LogicalDisk", detector._QUERY)
        for command in ("Set-", "New-", "Remove-", "Out-File", "Copy-", "Move-", "Format-", "Mount-", "Dismount-"):
            self.assertNotIn(command, detector._QUERY)


if __name__ == "__main__":
    unittest.main()
