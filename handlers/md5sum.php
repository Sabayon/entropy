<?php
	$pkgfile = $_GET['package'];
	$pkgarch = $_GET['arch'];
	$pkgfile = "../packages/" . $pkgarch . "/" . $pkgfile;
	$md5 = md5_file($pkgfile);
	echo($md5);
?>