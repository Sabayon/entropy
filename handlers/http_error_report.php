<?php

function insert_attachment($data,$mime,$filename,$hash) {

    $mymessage = "--PHP-mixed-".$hash."\r\n";
    $mymessage .= "Content-Type: ".$mime."; name=\"".$filename."\"\r\n";
    $mymessage .= "Content-Transfer-Encoding: base64\r\n";
    $mymessage .= "Content-Disposition: attachment\r\n";
    $mymessage .= chunk_split(base64_encode($data));
    $mymessage .= "--PHP-mixed-".$hash."--\r\n";
    return $mymessage;

}

$arch = $_POST['arch'];
$ip = $_SERVER['REMOTE_ADDR'];
$version = $_POST['version'];
$system_version = $_POST['system_version'];
$name = $_POST['name'];
$email = $_POST['email'];
$description = $_POST['description'];
$mail = "lxnay@sabayonlinux.org";
$subject = "Entropy Error Reporting Handler";
$random_hash = md5(date('r', time()));

if ($email) {
    $headers = "From: ".$email."\r\nReply-To: ".$email;
} else {
    $headers = "From: www-data@sabayonlinux.org\r\nReply-To: www-data@sabayonlinux.org";
}
$headers .= "\r\nContent-Type: multipart/mixed; boundary=\"PHP-mixed-".$random_hash."\"";

$message = "--PHP-mixed-".$random_hash."\r\n";
$message .= "Content-Type: multipart/alternative; boundary=\"PHP-alt-".$random_hash."\"\r\n";
$message .= "--PHP-alt-".$random_hash."\r\n";
$message .= "Content-Type: text/plain; charset=\"iso-8859-1\"\r\n";
$message .= "Content-Transfer-Encoding: 7bit\r\n";
$message .= "Hello, this is an Entropy error report.\r\n";
$message .= $_POST['stacktrace'];
$message .= "\n\n";
$message .= "Architecture: " . $arch . "\n";
$message .= "Arguments: " . $_POST['arguments'] . "\n";
$message .= "UID: " . $_POST['uid'] . "\n";
$message .= 'Name: ' . $name . "\n";
$message .= 'E-mail: ' . $email . "\n";
$message .= 'Description: ' . $description . "\n";
$message .= 'Version: ' . $version . "\n";
$message .= 'System Version: ' . $system_version . "\n";
$message .= 'IP: ' . $ip . "\n";
$message .= 'Date: ' . date("G:i d/F/Y") . "\n";
$message .= "--PHP-alt-".$random_hash."--\n";
$message .= insert_attachment($_POST['errordata'],'application/xml','errordata.txt',$random_hash);
$message .= insert_attachment($_POST['processes'],'application/xml','processes.txt',$random_hash);
$message .= insert_attachment($_POST['lspci'],'application/xml','lspci.txt',$random_hash);
$message .= insert_attachment($_POST['dmesg'],'application/xml','dmesg.txt',$random_hash);


if ($_POST['stacktrace'] && $_POST['arch'] && $ip) {
        $rc = mail($mail, $subject, $message, $headers);
        print_r($rc);
}
?>