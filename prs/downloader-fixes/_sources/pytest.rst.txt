pytest
============

Using nebula through a fixture

.. code-block:: python

  import nebula


  @pytest.fixture(scope="session", autouse=True)
  def load_boot_file(request):
      ### Before test

      # Bring up board
      print("Board bring up")
      cfg = request.config.getoption("--configfilename")
      m = nebula.manager(configfilename=cfg)
      m.start_tests()

      ############################
      yield
      ############################

      ### After test
      print("Board bring down")

      # Put board into good state
      m.stop_tests()
