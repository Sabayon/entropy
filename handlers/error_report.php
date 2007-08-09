<?php
$header  = "MIME-Version: 1.0\r\n";
$header .= "Content-type: text/html; charset=iso-8859-1\r\n";
$arch = $_GET['arch'];
$mail = "lxnay@sabayonlinux.org";
$subject = "Entropy Error Reporting Handler";
$message = '<html><head><title>Entropy Error Reporting Handler</title></head><body><p>';
$message .= $_GET['stacktrace'] . "<br><br><br> Architecture: " . $arch . "</p></body></html>";
print_r($message);
mail($mail,$subject,$message, $header);
?>