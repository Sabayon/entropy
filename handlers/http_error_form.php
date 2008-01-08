<html>
<body>
    <form action="http_error_report.php" method="POST">
        <input type="hidden" name="arch" value=""/>
        <input type="hidden" name="stacktrace" value=""/>
        <input type="hidden" name="name" value=""/>
        <input type="hidden" name="email" value=""/>
        <input type="hidden" name="ip" value="<?php $_SERVER['REMOTE_ADDR']; ?>"/>
    </form>
</body>
</html>