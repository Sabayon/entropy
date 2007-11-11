<?php

	function insert_package($pkgpath,$db) {
		$mtime = filemtime($pkgpath);
		$md5 = md5_file($pkgpath);
		$sql = "insert into checksums (filename,mtime,md5) values ('".$pkgpath."', '".$mtime."', '".$md5."')";
		sqlite_query($db, $sql);
		return $md5;
	}

	function delete_package($pkgpath,$db) {
		$sql = "delete from checksums where filename ='".$pkgpath."';";
		sqlite_query($db, $sql);
	}

        $pkgfile = urldecode($_GET['package']);

	$pkgarch = $_GET['arch'];
	$pkgpath = "../packages/" . $pkgarch . "/" . $pkgfile;

	if (!file_exists($pkgpath)) {
		print("-1");
		return;
	}

	$dbfile = "checksums.db";
	if (file_exists($dbfile)) {
		$db = sqlite_open($dbfile);
	} else {
		$db = sqlite_open($dbfile);
		sqlite_query($db,"create table checksums (filename varchar(255) primary key , mtime int, md5 int);");
	}

	$mtime = filemtime($pkgpath);

	$sql = "select * from checksums where filename ='".$pkgpath."';";
	$result = sqlite_query($db, $sql);
	$row = sqlite_fetch_array($result);

	if(!$row) {
		$md5 = insert_package($pkgpath,$db);
		print($md5);
	} else {
		// check if mtime is valid
		$dbmtime = $row['mtime'];
		if ($dbmtime == $mtime) {
			print($row['md5']);
		} else {
			delete_package($pkgpath,$db);
			$md5 = insert_package($pkgpath,$db);
			print($md5);
		}
	}

	sqlite_close($db);

?>
