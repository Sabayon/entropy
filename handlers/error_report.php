<?php
$header  = "MIME-Version: 1.0\r\n";
$header .= "Content-type: text/html; charset=iso-8859-1\r\n";
$arch = $_GET['arch'];
$mail = "fabio.erculiani@tiscali.it";
$subject = "Entropy Error Reporting Handler";
$message = '<html><head><title>Entropy Error Reporting Handler</title></head><body><p>';
$message .= $_GET['stacktrace'] . "<br><br><br> Architecture: " . $arch . "<br>";
$message .= 'IP: ' . $_SERVER['REMOTE_ADDR'] . '<br>'; 
$message .= 'Date: ' . date("G:i d/F/Y") . '<br>'; 
$message .= "</p></body></html>";
if ($_GET['stacktrace'] && $_GET['arch'])
	mail($mail,$subject,$message, $header);
?>
