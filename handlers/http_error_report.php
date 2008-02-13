<?php
$header  = "MIME-Version: 1.0\r\n";
$header .= "Content-type: text/plain; charset=iso-8859-1\r\n";
$arch = $_POST['arch'];
$ip = $_SERVER['REMOTE_ADDR'];
$version = $_POST['version'];
$name = $_POST['name'];
$email = $_POST['email'];
$description = $_POST['description'];
$mail = "fabio.erculiani@gmail.com";
$subject = "Entropy Error Reporting Handler";
$message = "Hello, this is an Entropy error report.\n";
$message .= $_POST['stacktrace'];
$message .= "\n\n";
$message .= $_POST['errordata'];
$message .= "\n\nArchitecture: " . $arch . "\n";
$message .= 'Name: ' . $name . "\n";
$message .= 'E-mail: ' . $email . "\n";
$message .= 'Description: ' . $description . "\n";
$message .= 'Version: ' . $version . "\n";
$message .= 'IP: ' . $ip . "\n";
$message .= 'Date: ' . date("G:i d/F/Y") . "\n";
$message .= "\n";
if ($_POST['stacktrace'] && $_POST['arch'] && $ip) {
        $rc = mail($mail,$subject,$message, $header);
        print_r($rc);
}
?>